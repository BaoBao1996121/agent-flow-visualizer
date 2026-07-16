"""Local append-only event storage with integrity verification.

JSONL is intentionally the first implementation: it is inspectable, easy to
share as a teaching exhibit, and requires no service.  The interface is kept
small so a PostgreSQL/outbox implementation can replace it for team and
production deployments.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

from .schema import AgentRuntimeEvent, CoreEventType


class EventStoreError(RuntimeError):
    pass


class DuplicateEventError(EventStoreError):
    pass


class CorruptLedgerError(EventStoreError):
    pass


@dataclass
class _RunIndex:
    next_seq: int = 0
    event_ids: set[str] = field(default_factory=set)
    last_hash: str | None = None


class JsonlEventStore:
    """Thread-safe append-only store, partitioned by run."""

    def __init__(self, root: str | Path, *, fsync: bool = False):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.fsync = fsync
        self._global_lock = threading.RLock()
        self._run_locks: dict[str, threading.RLock] = {}
        self._indexes: dict[str, _RunIndex] = {}

    def append(self, event: AgentRuntimeEvent | dict) -> AgentRuntimeEvent:
        """Validate, stamp, hash, and append one event."""

        parsed = self._parse_event(event)
        return self.append_many([parsed])[0]

    def append_many(
        self, events: Iterable[AgentRuntimeEvent | dict]
    ) -> list[AgentRuntimeEvent]:
        """Append a same-run batch without allowing a partial duplicate batch."""

        parsed = [self._parse_event(event) for event in events]
        if not parsed:
            return []

        run_id = parsed[0].run_id
        if any(event.run_id != run_id for event in parsed):
            raise ValueError("append_many requires all events to share one run_id")

        lock = self._lock_for(run_id)
        with lock:
            index = self._index_for(run_id)
            batch_ids = [event.event_id for event in parsed]
            if len(set(batch_ids)) != len(batch_ids):
                raise DuplicateEventError("event_id is duplicated within the batch")
            duplicates = index.event_ids.intersection(batch_ids)
            if duplicates:
                raise DuplicateEventError(
                    f"event_id already exists: {sorted(duplicates)[0]}"
                )

            stamped: list[AgentRuntimeEvent] = []
            previous_hash = index.last_hash
            next_seq = index.next_seq
            for event in parsed:
                stored = event.with_ingest_metadata(
                    ingest_seq=next_seq,
                    previous_event_hash=previous_hash,
                )
                stamped.append(stored)
                previous_hash = stored.integrity.event_hash if stored.integrity else None
                next_seq += 1

            run_dir = self._run_dir(run_id)
            run_dir.mkdir(parents=True, exist_ok=True)
            self._ensure_manifest(run_id, stamped[0])
            ledger_path = run_dir / "events.jsonl"
            with ledger_path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.writelines(event.to_json_line() for event in stamped)
                stream.flush()
                if self.fsync:
                    os.fsync(stream.fileno())

            index.next_seq = next_seq
            index.event_ids.update(batch_ids)
            index.last_hash = previous_hash
            self._update_manifest(run_id, len(stamped), stamped[-1])
            return stamped

    def read_run(
        self,
        run_id: str,
        *,
        from_seq: int = 0,
        to_seq: int | None = None,
        event_types: Iterable[CoreEventType | str] | None = None,
    ) -> Iterator[AgentRuntimeEvent]:
        """Read a run in authoritative ingest order."""

        if from_seq < 0:
            raise ValueError("from_seq cannot be negative")
        if to_seq is not None and to_seq < from_seq:
            raise ValueError("to_seq cannot be smaller than from_seq")

        wanted = None
        if event_types is not None:
            wanted = {
                item.value if isinstance(item, CoreEventType) else str(item)
                for item in event_types
            }

        ledger_path = self._run_dir(run_id) / "events.jsonl"
        if not ledger_path.exists():
            return

        with ledger_path.open("r", encoding="utf-8") as stream:
            for line_no, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    event = AgentRuntimeEvent.model_validate_json(line)
                except Exception as exc:
                    raise CorruptLedgerError(
                        f"invalid event at {ledger_path}:{line_no}: {exc}"
                    ) from exc
                if event.run_id != run_id:
                    raise CorruptLedgerError(
                        f"run mismatch at {ledger_path}:{line_no}"
                    )
                seq = event.clock.ingest_seq
                if seq is None:
                    raise CorruptLedgerError(
                        f"missing ingest_seq at {ledger_path}:{line_no}"
                    )
                if seq < from_seq:
                    continue
                if to_seq is not None and seq > to_seq:
                    break
                if wanted is None or event.event_type in wanted:
                    yield event

    def get_event(self, run_id: str, event_id: str) -> AgentRuntimeEvent | None:
        for event in self.read_run(run_id):
            if event.event_id == event_id:
                return event
        return None

    def list_runs(self) -> list[dict]:
        manifests: list[dict] = []
        for path in self.root.glob("*/manifest.json"):
            try:
                manifests.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return sorted(
            manifests,
            key=lambda item: item.get("updated_at", item.get("created_at", "")),
            reverse=True,
        )

    def get_manifest(self, run_id: str) -> dict | None:
        """Return the rebuildable run manifest, or ``None`` when absent/invalid."""

        path = self._run_dir(run_id) / "manifest.json"
        if path.exists():
            try:
                manifest = json.loads(path.read_text(encoding="utf-8"))
                if manifest.get("run_id") == run_id:
                    return manifest
            except (OSError, json.JSONDecodeError):
                pass
        # The ledger is authoritative. Reconstruct enough metadata in memory
        # when the optional manifest is missing or torn.
        events = list(self.read_run(run_id))
        if not events:
            return None
        first, last = events[0], events[-1]
        return {
            "run_id": run_id,
            "schema_version": first.schema_version,
            "event_count": len(events),
            "project_id": first.project_id,
            "session_id": first.session_id,
            "title": first.payload.get("title", run_id),
            "synthetic": bool(first.payload.get("synthetic", False)),
            "source_adapter": first.source.adapter,
            "last_event_type": last.event_type,
            "last_event_hash": (
                last.integrity.event_hash if last.integrity else None
            ),
        }

    def verify_run(self, run_id: str) -> dict:
        """Verify sequence order, IDs, and the complete hash chain."""

        expected_seq = 0
        previous_hash = None
        seen_ids: set[str] = set()
        errors: list[str] = []
        event_count = 0

        try:
            for event in self.read_run(run_id):
                event_count += 1
                if event.clock.ingest_seq != expected_seq:
                    errors.append(
                        f"sequence {event.clock.ingest_seq} found; expected {expected_seq}"
                    )
                if event.event_id in seen_ids:
                    errors.append(f"duplicate event_id {event.event_id}")
                seen_ids.add(event.event_id)

                integrity = event.integrity
                if integrity is None:
                    errors.append(f"event {event.event_id} has no integrity metadata")
                else:
                    if integrity.previous_event_hash != previous_hash:
                        errors.append(
                            f"event {event.event_id} has a broken previous hash"
                        )
                    calculated = event.calculate_hash()
                    if integrity.event_hash != calculated:
                        errors.append(f"event {event.event_id} hash does not match")
                    previous_hash = integrity.event_hash
                expected_seq += 1
        except CorruptLedgerError as exc:
            errors.append(str(exc))

        return {
            "run_id": run_id,
            "valid": not errors,
            "event_count": event_count,
            "last_event_hash": previous_hash,
            "errors": errors,
        }

    @staticmethod
    def _parse_event(event: AgentRuntimeEvent | dict) -> AgentRuntimeEvent:
        if isinstance(event, AgentRuntimeEvent):
            return event
        return AgentRuntimeEvent.model_validate(event)

    def _lock_for(self, run_id: str) -> threading.RLock:
        with self._global_lock:
            return self._run_locks.setdefault(run_id, threading.RLock())

    def _index_for(self, run_id: str) -> _RunIndex:
        if run_id in self._indexes:
            return self._indexes[run_id]

        index = _RunIndex()
        ledger_path = self._run_dir(run_id) / "events.jsonl"
        if ledger_path.exists():
            for event in self.read_run(run_id):
                if event.event_id in index.event_ids:
                    raise CorruptLedgerError(
                        f"duplicate event_id in ledger: {event.event_id}"
                    )
                index.event_ids.add(event.event_id)
                if event.clock.ingest_seq is None:
                    raise CorruptLedgerError(
                        f"missing ingest_seq on event {event.event_id}"
                    )
                index.next_seq = max(index.next_seq, event.clock.ingest_seq + 1)
                index.last_hash = (
                    event.integrity.event_hash if event.integrity else None
                )
        self._indexes[run_id] = index
        return index

    def _run_dir(self, run_id: str) -> Path:
        slug = re.sub(r"[^A-Za-z0-9._-]+", "-", run_id).strip("-._")[:48]
        if not slug:
            slug = "run"
        digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:12]
        return self.root / f"{slug}-{digest}"

    def _ensure_manifest(
        self, run_id: str, first_event: AgentRuntimeEvent
    ) -> None:
        path = self._run_dir(run_id) / "manifest.json"
        if path.exists():
            return
        now = datetime.now(timezone.utc).isoformat()
        manifest = {
            "run_id": run_id,
            "schema_version": first_event.schema_version,
            "created_at": now,
            "updated_at": now,
            "event_count": 0,
            "project_id": first_event.project_id,
            "session_id": first_event.session_id,
            "title": first_event.payload.get("title", run_id),
            "synthetic": bool(first_event.payload.get("synthetic", False)),
            "source_adapter": first_event.source.adapter,
            "last_event_type": None,
        }
        self._write_manifest(path, manifest)

    def _update_manifest(
        self, run_id: str, appended_count: int, last_event: AgentRuntimeEvent
    ) -> None:
        path = self._run_dir(run_id) / "manifest.json"
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {"run_id": run_id, "created_at": datetime.now(timezone.utc).isoformat()}
        manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
        manifest["event_count"] = int(manifest.get("event_count", 0)) + appended_count
        manifest["last_event_type"] = last_event.event_type
        manifest["last_event_hash"] = (
            last_event.integrity.event_hash if last_event.integrity else None
        )
        self._write_manifest(path, manifest)

    @staticmethod
    def _write_manifest(path: Path, data: dict) -> None:
        # The ledger is the source of truth and the manifest is a rebuildable
        # index.  A direct, fsynced write is used here because Windows scanners
        # can hold the destination briefly and make os.replace fail even while
        # this process owns the per-run lock.  The JSONL store is intentionally
        # single-process/thread-safe; production multi-process ingestion uses a
        # transactional database store.
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
