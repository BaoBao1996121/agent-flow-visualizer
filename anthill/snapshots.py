"""Immutable, versioned world projection snapshots.

Snapshots are acceleration artifacts. The event ledger remains authoritative;
snapshot corruption is detectable and callers can recompute from events.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .projections.world import REDUCER_VERSION, WorldState


SNAPSHOT_VERSION = "0.1.0"


class SnapshotError(RuntimeError):
    pass


class CorruptSnapshotError(SnapshotError):
    pass


class WorldSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_version: str = SNAPSHOT_VERSION
    reducer_version: str = REDUCER_VERSION
    run_id: str
    seq: int = Field(ge=-1)
    event_id: str | None = None
    event_hash: str | None = None
    state_hash: str
    created_at: datetime
    state: WorldState

    @classmethod
    def create(
        cls,
        state: WorldState,
        *,
        event_hash: str | None,
    ) -> "WorldSnapshot":
        return cls(
            run_id=state.run_id,
            seq=state.cursor_seq,
            event_id=state.cursor_event_id,
            event_hash=event_hash,
            state_hash=calculate_state_hash(state),
            created_at=datetime.now(timezone.utc),
            state=state,
        )


def calculate_state_hash(state: WorldState) -> str:
    canonical = json.dumps(
        state.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class JsonWorldSnapshotStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, snapshot: WorldSnapshot) -> WorldSnapshot:
        self._verify_model(snapshot)
        path = self._snapshot_path(
            snapshot.run_id,
            snapshot.reducer_version,
            snapshot.seq,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            existing = self._load_path(path)
            if existing.state_hash != snapshot.state_hash:
                raise SnapshotError(
                    f"snapshot already exists with different state hash at seq {snapshot.seq}"
                )
            return existing
        # Snapshot names are immutable, so exclusive create avoids replacement
        # races and keeps partial/corrupt files visible to integrity checks.
        try:
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(snapshot.model_dump_json(indent=2))
                stream.write("\n")
        except FileExistsError:
            return self.save(snapshot)
        return snapshot

    def latest(
        self,
        run_id: str,
        *,
        reducer_version: str = REDUCER_VERSION,
        at_seq: int | None = None,
    ) -> WorldSnapshot | None:
        directory = self._version_dir(run_id, reducer_version)
        if not directory.exists():
            return None
        candidates = []
        for path in directory.glob("*.json"):
            try:
                seq = int(path.stem)
            except ValueError:
                continue
            if at_seq is None or seq <= at_seq:
                candidates.append((seq, path))
        if not candidates:
            return None
        _, path = max(candidates, key=lambda item: item[0])
        return self._load_path(path)

    def list_run(
        self,
        run_id: str,
        *,
        reducer_version: str = REDUCER_VERSION,
    ) -> list[dict]:
        directory = self._version_dir(run_id, reducer_version)
        if not directory.exists():
            return []
        result = []
        for path in sorted(directory.glob("*.json")):
            try:
                snapshot = self._load_path(path)
                result.append(
                    {
                        "seq": snapshot.seq,
                        "event_id": snapshot.event_id,
                        "event_hash": snapshot.event_hash,
                        "state_hash": snapshot.state_hash,
                        "reducer_version": snapshot.reducer_version,
                        "created_at": snapshot.created_at.isoformat(),
                        "valid": True,
                    }
                )
            except CorruptSnapshotError as exc:
                result.append(
                    {
                        "seq": int(path.stem) if path.stem.isdigit() else None,
                        "reducer_version": reducer_version,
                        "valid": False,
                        "error": str(exc),
                    }
                )
        return result

    def _load_path(self, path: Path) -> WorldSnapshot:
        try:
            snapshot = WorldSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise CorruptSnapshotError(f"invalid snapshot {path.name}: {exc}") from exc
        self._verify_model(snapshot)
        return snapshot

    @staticmethod
    def _verify_model(snapshot: WorldSnapshot) -> None:
        if snapshot.run_id != snapshot.state.run_id:
            raise CorruptSnapshotError("snapshot run_id does not match state")
        if snapshot.seq != snapshot.state.cursor_seq:
            raise CorruptSnapshotError("snapshot sequence does not match state cursor")
        if snapshot.seq >= 0 and (not snapshot.event_id or not snapshot.event_hash):
            raise CorruptSnapshotError("snapshot is not anchored to a ledger event hash")
        calculated = calculate_state_hash(snapshot.state)
        if calculated != snapshot.state_hash:
            raise CorruptSnapshotError("snapshot state hash does not match")

    def _snapshot_path(self, run_id: str, reducer_version: str, seq: int) -> Path:
        return self._version_dir(run_id, reducer_version) / f"{seq:020d}.json"

    def _version_dir(self, run_id: str, reducer_version: str) -> Path:
        slug = re.sub(r"[^A-Za-z0-9._-]+", "-", run_id).strip("-._")[:40] or "run"
        digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:12]
        version = re.sub(r"[^A-Za-z0-9._-]+", "-", reducer_version)[:40]
        return self.root / f"{slug}-{digest}" / version
