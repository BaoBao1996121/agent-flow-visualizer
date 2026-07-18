"""Local append-only event storage with integrity verification.

JSONL is intentionally the first implementation: it is inspectable, easy to
share as a teaching exhibit, and requires no service.  The interface is kept
small so a PostgreSQL/outbox implementation can replace it for team and
production deployments.
"""

from __future__ import annotations

import hashlib
import json
import logging
import mmap
import os
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator

from .run_lifecycle import CANONICAL_RUN_STATUSES, fold_run_status
from .schema import AgentRuntimeEvent, CoreEventType, is_addressable_run_id


LOGGER = logging.getLogger(__name__)
_MANIFEST_CACHE_CHECKSUM_FIELD = "_cache_checksum"


class EventStoreError(RuntimeError):
    pass


class DuplicateEventError(EventStoreError):
    pass


class RunAlreadyExistsError(EventStoreError):
    pass


class CorruptLedgerError(EventStoreError):
    def __init__(self, message: str, *, error_type: str = "corrupt_ledger"):
        super().__init__(message)
        self.error_type = error_type


@dataclass
class _RunIndex:
    next_seq: int = 0
    event_ids: set[str] = field(default_factory=set)
    last_hash: str | None = None
    ledger_digest: str | None = None


class JsonlEventStore:
    """Thread-safe append-only store, partitioned by run."""
    _RUN_LOCK_STRIPES = 64

    def __init__(self, root: str | Path, *, fsync: bool = False):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.fsync = fsync
        self._global_lock = threading.RLock()
        self._run_locks = tuple(threading.RLock() for _ in range(self._RUN_LOCK_STRIPES))
        self._indexes: dict[str, _RunIndex] = {}
        self._run_ids_by_directory: dict[str, str] = {}

    def append(self, event: AgentRuntimeEvent | dict) -> AgentRuntimeEvent:
        """Validate, stamp, hash, and append one event."""

        parsed = self._parse_event(event)
        return self.append_many([parsed])[0]

    def append_many(
        self,
        events: Iterable[AgentRuntimeEvent | dict],
        *,
        require_empty: bool = False,
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
            if require_empty and index.next_seq != 0:
                raise RunAlreadyExistsError("run already exists")
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
            with self._global_lock:
                self._run_ids_by_directory[run_dir.name] = run_id
            ledger_path = run_dir / "events.jsonl"
            with ledger_path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.writelines(event.to_json_line() for event in stamped)
                stream.flush()
                if self.fsync:
                    os.fsync(stream.fileno())

            index.next_seq = next_seq
            index.event_ids.update(batch_ids)
            index.last_hash = previous_hash
            index.ledger_digest = self._ledger_digest(run_id)
            self._update_manifest(run_id, stamped)
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

        with self._lock_for(run_id):
            try:
                last_event = self._last_event_from_ledger(run_id)
            except CorruptLedgerError:
                # Preserve the full reader's stable error classification for
                # malformed records and run mismatches. A HEAD anchor can only
                # be compared when the candidate ledger head is parseable.
                last_event = None
                head_is_comparable = False
            else:
                head_is_comparable = True
            if head_is_comparable:
                ledger_event_count = (
                    0
                    if last_event is None
                    else (last_event.clock.ingest_seq or 0) + 1
                )
                ledger_last_hash = (
                    None
                    if last_event is None or last_event.integrity is None
                    else last_event.integrity.event_hash
                )
                self._assert_manifest_head_compatible(
                    run_id, ledger_event_count, ledger_last_hash
                )

        ledger_path = self._run_dir(run_id) / "events.jsonl"
        if not ledger_path.exists():
            return
        ledger_ref = self._ledger_reference(ledger_path)

        with ledger_path.open("r", encoding="utf-8") as stream:
            for line_no, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    event = AgentRuntimeEvent.model_validate_json(
                        line,
                        context={"allow_legacy_run_id": True},
                    )
                except Exception:
                    raise CorruptLedgerError(
                        f"{ledger_ref} line {line_no}: invalid_event",
                        error_type="invalid_event",
                    ) from None
                if event.run_id != run_id:
                    raise CorruptLedgerError(
                        f"{ledger_ref} line {line_no}: run_mismatch",
                        error_type="run_mismatch",
                    )
                seq = event.clock.ingest_seq
                if seq is None:
                    raise CorruptLedgerError(
                        f"{ledger_ref} line {line_no}: missing_sequence",
                        error_type="missing_sequence",
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
        return self.list_runs_with_diagnostics(diagnostic_limit=0)["items"]

    def list_runs_with_diagnostics(
        self,
        *,
        diagnostic_limit: int | None = None,
    ) -> dict[str, object]:
        if diagnostic_limit is not None and diagnostic_limit < 0:
            raise ValueError("diagnostic_limit cannot be negative")
        manifests: list[dict] = []
        discovery_errors: list[dict] = []
        discovery_error_count = 0

        def record_discovery_error(ledger_ref: str, error_type: str) -> None:
            nonlocal discovery_error_count
            discovery_error_count += 1
            if diagnostic_limit is None or len(discovery_errors) < diagnostic_limit:
                discovery_errors.append(
                    {"ledger_ref": ledger_ref, "error_type": error_type}
                )

        for ledger_path in sorted(self.root.glob("*/events.jsonl")):
            ledger_ref = self._ledger_reference(ledger_path)
            try:
                with self._global_lock:
                    run_id_hint = self._run_ids_by_directory.get(ledger_path.parent.name)
                run_id = run_id_hint or self._run_id_from_discovery_boundary(ledger_path)
                if not is_addressable_run_id(run_id):
                    record_discovery_error(ledger_ref, "unsafe_legacy_run_id")
                    continue
                with self._lock_for(run_id):
                    discovered_run_id = self._run_id_from_discovery_boundary(ledger_path)
                run_id = discovered_run_id
                if ledger_path.resolve() != (
                    self._run_dir(run_id) / "events.jsonl"
                ).resolve():
                    record_discovery_error(ledger_ref, "misplaced_ledger")
                    continue
                manifest = self.get_manifest(run_id)
            except CorruptLedgerError as exc:
                record_discovery_error(ledger_ref, exc.error_type)
                continue
            except (OSError, ValueError):
                record_discovery_error(ledger_ref, "unreadable_ledger")
                continue
            if manifest is not None:
                manifests.append(manifest)

        for manifest_path in sorted(self.root.glob("*/manifest.json")):
            ledger_path = manifest_path.parent / "events.jsonl"
            if ledger_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not self._manifest_checksum_is_valid(manifest):
                continue
            run_id = manifest.get("run_id")
            event_count = manifest.get("event_count")
            if type(event_count) is not int or event_count <= 0:
                continue
            ledger_ref = self._ledger_reference(ledger_path)
            if not isinstance(run_id, str) or not is_addressable_run_id(run_id):
                record_discovery_error(ledger_ref, "unsafe_legacy_run_id")
                continue
            if manifest_path.parent.resolve() != self._run_dir(run_id).resolve():
                record_discovery_error(ledger_ref, "misplaced_manifest_anchor")
                continue
            record_discovery_error(ledger_ref, "truncated_ledger")

        return {
            "items": sorted(
                manifests,
                key=lambda item: item.get("updated_at", item.get("created_at", "")),
                reverse=True,
            ),
            "discovery_errors": sorted(
                discovery_errors,
                key=lambda item: item["ledger_ref"],
            ),
            "discovery_error_count": discovery_error_count,
            "diagnostics_truncated": discovery_error_count > len(discovery_errors),
        }

    def get_manifest(self, run_id: str) -> dict | None:
        """Return the rebuildable run manifest, or ``None`` when absent/invalid."""

        with self._lock_for(run_id):
            path = self._run_dir(run_id) / "manifest.json"
            last_event = self._last_event_from_ledger(run_id)
            ledger_event_count = (
                0 if last_event is None else (last_event.clock.ingest_seq or 0) + 1
            )
            ledger_last_hash = (
                None if last_event is None or last_event.integrity is None else last_event.integrity.event_hash
            )
            self._assert_manifest_head_compatible(run_id, ledger_event_count, ledger_last_hash)
            if last_event is None:
                return None
            if path.exists():
                try:
                    manifest = json.loads(path.read_text(encoding="utf-8"))
                    if self._manifest_matches_ledger_head(
                        manifest,
                        run_id,
                        last_event,
                    ):
                        return self._public_manifest(manifest)
                except (OSError, json.JSONDecodeError, ValueError):
                    pass
            manifest = self._manifest_from_ledger(run_id)
            if manifest is not None:
                self._write_manifest_best_effort(path, manifest)
            return manifest

    def _manifest_from_ledger(self, run_id: str) -> dict | None:
        """Reconstruct manifest facts from the authoritative event ledger."""

        events = list(self._iter_validated_run(run_id))
        if not events:
            return None
        first, last = events[0], events[-1]
        return {
            "run_id": run_id,
            "schema_version": first.schema_version,
            "created_at": first.clock.observed_at.isoformat(),
            "updated_at": last.clock.observed_at.isoformat(),
            "event_count": len(events),
            "project_id": first.project_id,
            "session_id": first.session_id,
            "title": first.payload.get("title", run_id),
            "synthetic": bool(first.payload.get("synthetic", False)),
            "source_adapter": first.source.adapter,
            "run_status": fold_run_status(events),
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
        payload = event.model_dump(mode="python") if isinstance(event, AgentRuntimeEvent) else event
        # Legacy validation context belongs exclusively to storage reads.
        return AgentRuntimeEvent.model_validate(payload)

    def _lock_for(self, run_id: str) -> threading.RLock:
        stripe = int.from_bytes(hashlib.sha256(run_id.encode("utf-8")).digest()[:8])
        return self._run_locks[stripe % len(self._run_locks)]

    def _index_for(self, run_id: str) -> _RunIndex:
        with self._lock_for(run_id):
            ledger_digest = self._ledger_digest(run_id)
            existing = self._indexes.get(run_id)
            if existing is not None and existing.ledger_digest == ledger_digest:
                self._assert_manifest_head_compatible(
                    run_id,
                    existing.next_seq,
                    existing.last_hash,
                )
                return existing

            index = _RunIndex()
            for event in self._iter_validated_run(run_id):
                index.event_ids.add(event.event_id)
                index.next_seq = (event.clock.ingest_seq or 0) + 1
                index.last_hash = event.integrity.event_hash if event.integrity else None
            validated_digest = self._ledger_digest(run_id)
            if validated_digest != ledger_digest:
                raise CorruptLedgerError(
                    "ledger changed while its hash chain was being validated",
                    error_type="ledger_changed_during_validation",
                )
            index.ledger_digest = validated_digest
            self._assert_manifest_head_compatible(
                run_id,
                index.next_seq,
                index.last_hash,
            )
            self._indexes[run_id] = index
            return index

    def _ledger_digest(self, run_id: str) -> str:
        digest = hashlib.sha256()
        path = self._run_dir(run_id) / "events.jsonl"
        try:
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        except FileNotFoundError:
            pass
        return digest.hexdigest()

    @staticmethod
    def _ledger_reference(path: Path) -> str:
        digest = hashlib.sha256(path.parent.name.encode("utf-8")).hexdigest()[:24]
        return f"ledger:{digest}"

    @staticmethod
    def _run_id_from_ledger(path: Path) -> str:
        try:
            with path.open("r", encoding="utf-8") as stream:
                for line in stream:
                    if line.strip():
                        return AgentRuntimeEvent.model_validate_json(
                            line,
                            context={"allow_legacy_run_id": True},
                        ).run_id
        except (OSError, ValueError) as exc:
            raise CorruptLedgerError(
                "ledger first event is invalid",
                error_type="invalid_first_event",
            ) from exc
        raise CorruptLedgerError("ledger is empty", error_type="empty_ledger")

    def _run_id_from_discovery_boundary(self, ledger_path: Path) -> str:
        """Recover an empty truncated ledger's identity from its valid cache anchor."""

        try:
            return self._run_id_from_ledger(ledger_path)
        except CorruptLedgerError as exc:
            if exc.error_type != "empty_ledger":
                raise
            try:
                manifest = json.loads(
                    (ledger_path.parent / "manifest.json").read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                raise exc from None
            run_id = manifest.get("run_id") if isinstance(manifest, dict) else None
            event_count = manifest.get("event_count") if isinstance(manifest, dict) else None
            if (
                not isinstance(run_id, str)
                or type(event_count) is not int
                or event_count <= 0
                or not self._manifest_checksum_is_valid(manifest)
            ):
                raise exc
            return run_id

    def _iter_validated_run(self, run_id: str) -> Iterator[AgentRuntimeEvent]:
        expected_seq = 0
        previous_hash = None
        seen_ids: set[str] = set()
        for event in self.read_run(run_id):
            if event.clock.ingest_seq != expected_seq:
                raise CorruptLedgerError(
                    f"sequence {event.clock.ingest_seq} found; expected {expected_seq}"
                )
            if event.event_id in seen_ids:
                raise CorruptLedgerError(
                    f"duplicate event_id in ledger: {event.event_id}"
                )
            integrity = event.integrity
            if integrity is None:
                raise CorruptLedgerError(
                    f"event {event.event_id} has no integrity metadata"
                )
            if integrity.previous_event_hash != previous_hash:
                raise CorruptLedgerError(
                    f"event {event.event_id} has a broken previous hash"
                )
            if integrity.event_hash != event.calculate_hash():
                raise CorruptLedgerError(
                    f"event {event.event_id} hash does not match"
                )
            seen_ids.add(event.event_id)
            previous_hash = integrity.event_hash
            expected_seq += 1
            yield event

    def _last_event_from_ledger(self, run_id: str) -> AgentRuntimeEvent | None:
        path = self._run_dir(run_id) / "events.jsonl"
        try:
            if not path.exists() or path.stat().st_size == 0:
                return None
            with path.open("rb") as stream, mmap.mmap(
                stream.fileno(),
                0,
                access=mmap.ACCESS_READ,
            ) as data:
                end = len(data)
                line = b""
                while end > 0:
                    newline = data.rfind(b"\n", 0, end)
                    line = data[newline + 1 : end].strip()
                    if line:
                        break
                    if newline < 0:
                        return None
                    end = newline
            event = AgentRuntimeEvent.model_validate_json(
                line,
                context={"allow_legacy_run_id": True},
            )
        except (OSError, ValueError) as exc:
            raise CorruptLedgerError(
                "ledger last event is invalid",
                error_type="invalid_last_event",
            ) from exc
        if event.run_id != run_id:
            raise CorruptLedgerError("ledger last event has a run mismatch")
        return event

    def _run_dir(self, run_id: str) -> Path:
        slug = re.sub(r"[^A-Za-z0-9._-]+", "-", run_id).strip("-._")[:48]
        if not slug:
            slug = "run"
        digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:12]
        return self.root / f"{slug}-{digest}"

    def _update_manifest(
        self, run_id: str, appended: list[AgentRuntimeEvent]
    ) -> None:
        path = self._run_dir(run_id) / "manifest.json"
        if appended[0].clock.ingest_seq == 0:
            manifest = self._manifest_from_ledger(run_id)
            reconstructed = manifest is not None
        else:
            try:
                manifest = json.loads(path.read_text(encoding="utf-8"))
                if not self._manifest_matches_append_boundary(
                    manifest,
                    run_id,
                    appended[0],
                ):
                    raise ValueError("manifest does not match its ledger append boundary")
                reconstructed = False
            except (OSError, json.JSONDecodeError, ValueError):
                manifest = self._manifest_from_ledger(run_id)
                reconstructed = manifest is not None
        if manifest is None:
            raise CorruptLedgerError(f"cannot reconstruct manifest for {run_id}")
        if not reconstructed:
            manifest["event_count"] = (
                int(manifest.get("event_count", 0)) + len(appended)
            )
            manifest["run_status"] = fold_run_status(
                appended, initial=str(manifest.get("run_status", "unknown"))
            )
        last_event = appended[-1]
        manifest["updated_at"] = last_event.clock.observed_at.isoformat()
        manifest["last_event_type"] = last_event.event_type
        manifest["last_event_hash"] = (
            last_event.integrity.event_hash if last_event.integrity else None
        )
        self._write_manifest_best_effort(path, manifest)

    @staticmethod
    def _manifest_matches_ledger_head(
        manifest: object,
        run_id: str,
        last_event: AgentRuntimeEvent,
    ) -> bool:
        if not isinstance(manifest, dict) or manifest.get("run_id") != run_id:
            return False
        event_count = manifest.get("event_count")
        status = manifest.get("run_status")
        last_hash = last_event.integrity.event_hash if last_event.integrity else None
        return (
            type(event_count) is int
            and event_count == (last_event.clock.ingest_seq or 0) + 1
            and manifest.get("last_event_hash") == last_hash
            and isinstance(status, str)
            and status in CANONICAL_RUN_STATUSES
            and JsonlEventStore._manifest_checksum_is_valid(manifest)
            and JsonlEventStore._is_aware_manifest_time(manifest.get("created_at"))
            and JsonlEventStore._is_aware_manifest_time(manifest.get("updated_at"))
        )

    @staticmethod
    def _manifest_matches_append_boundary(
        manifest: object,
        run_id: str,
        first_appended: AgentRuntimeEvent,
    ) -> bool:
        if not isinstance(manifest, dict) or manifest.get("run_id") != run_id:
            return False
        event_count = manifest.get("event_count")
        status = manifest.get("run_status")
        previous_hash = (
            first_appended.integrity.previous_event_hash
            if first_appended.integrity
            else None
        )
        return (
            type(event_count) is int
            and event_count == first_appended.clock.ingest_seq
            and manifest.get("last_event_hash") == previous_hash
            and isinstance(status, str)
            and status in CANONICAL_RUN_STATUSES
            and JsonlEventStore._manifest_checksum_is_valid(manifest)
            and JsonlEventStore._is_aware_manifest_time(manifest.get("created_at"))
            and JsonlEventStore._is_aware_manifest_time(manifest.get("updated_at"))
        )

    def _assert_manifest_head_compatible(
        self,
        run_id: str,
        ledger_event_count: int,
        ledger_last_hash: str | None,
    ) -> None:
        path = self._run_dir(run_id) / "manifest.json"
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if (
            not isinstance(manifest, dict)
            or manifest.get("run_id") != run_id
            or not self._manifest_checksum_is_valid(manifest)
        ):
            return
        manifest_event_count = manifest.get("event_count")
        if type(manifest_event_count) is not int or manifest_event_count < 0:
            return
        if manifest_event_count > ledger_event_count:
            raise CorruptLedgerError(
                "ledger is behind its validated manifest head",
                error_type="truncated_ledger",
            )
        if (
            manifest_event_count == ledger_event_count
            and manifest.get("last_event_hash") != ledger_last_hash
        ):
            raise CorruptLedgerError(
                "ledger disagrees with its validated manifest head",
                error_type="divergent_ledger",
            )

    @staticmethod
    def _manifest_cache_checksum(manifest: dict) -> str:
        public_fields = {
            key: value
            for key, value in manifest.items()
            if key != _MANIFEST_CACHE_CHECKSUM_FIELD
        }
        canonical = json.dumps(
            public_fields,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def _manifest_checksum_is_valid(manifest: object) -> bool:
        if not isinstance(manifest, dict):
            return False
        checksum = manifest.get(_MANIFEST_CACHE_CHECKSUM_FIELD)
        return (
            isinstance(checksum, str)
            and checksum == JsonlEventStore._manifest_cache_checksum(manifest)
        )

    @staticmethod
    def _public_manifest(manifest: dict) -> dict:
        public = dict(manifest)
        public.pop(_MANIFEST_CACHE_CHECKSUM_FIELD, None)
        return public

    @staticmethod
    def _is_aware_manifest_time(value: object) -> bool:
        if not isinstance(value, str):
            return False
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False
        return parsed.tzinfo is not None and parsed.utcoffset() is not None

    def _write_manifest_best_effort(self, path: Path, data: dict) -> None:
        try:
            cached = dict(data)
            cached[_MANIFEST_CACHE_CHECKSUM_FIELD] = self._manifest_cache_checksum(cached)
            self._write_manifest(path, cached)
        except OSError:
            LOGGER.warning(
                "manifest cache write failed for run directory %s",
                self._ledger_reference(path),
            )

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
