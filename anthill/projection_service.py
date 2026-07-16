"""Snapshot-aware projection service over the authoritative event store."""

from __future__ import annotations

from dataclasses import dataclass, field

from .projections.world import REDUCER_VERSION, WorldState, project_world
from .snapshots import (
    CorruptSnapshotError,
    JsonWorldSnapshotStore,
    SnapshotError,
    WorldSnapshot,
)
from .store import JsonlEventStore


@dataclass
class ProjectionResult:
    state: WorldState
    head_seq: int
    target_seq: int
    snapshot_seq: int | None
    events_replayed: int
    warnings: list[str] = field(default_factory=list)


class WorldProjectionService:
    def __init__(
        self,
        event_store: JsonlEventStore,
        snapshot_store: JsonWorldSnapshotStore,
        *,
        snapshot_interval: int = 250,
    ):
        if snapshot_interval < 1:
            raise ValueError("snapshot_interval must be positive")
        self.event_store = event_store
        self.snapshot_store = snapshot_store
        self.snapshot_interval = snapshot_interval

    def project(
        self,
        run_id: str,
        *,
        at_seq: int | None = None,
        force_snapshot: bool = False,
    ) -> ProjectionResult | None:
        manifest = self.event_store.get_manifest(run_id)
        if manifest is None:
            return None
        event_count = int(manifest.get("event_count", 0))
        if event_count <= 0:
            return None
        head_seq = event_count - 1
        target_seq = head_seq if at_seq is None else min(at_seq, head_seq)
        warnings: list[str] = []
        snapshot = None
        try:
            snapshot = self.snapshot_store.latest(
                run_id,
                reducer_version=REDUCER_VERSION,
                at_seq=target_seq,
            )
            if snapshot is not None:
                anchor = self.event_store.get_event(
                    run_id, snapshot.event_id or ""
                )
                anchor_hash = (
                    anchor.integrity.event_hash
                    if anchor and anchor.integrity
                    else None
                )
                if anchor_hash != snapshot.event_hash:
                    raise CorruptSnapshotError(
                        "snapshot event hash is not anchored to the current ledger"
                    )
        except CorruptSnapshotError as exc:
            warnings.append(f"snapshot ignored: {exc}")
            snapshot = None

        initial_state = snapshot.state if snapshot else None
        from_seq = snapshot.seq + 1 if snapshot else 0
        tail = (
            []
            if from_seq > target_seq
            else list(
                self.event_store.read_run(
                    run_id,
                    from_seq=from_seq,
                    to_seq=target_seq,
                )
            )
        )
        state = project_world(
            tail,
            run_id=run_id,
            initial_state=initial_state,
        )
        result = ProjectionResult(
            state=state,
            head_seq=head_seq,
            target_seq=target_seq,
            snapshot_seq=snapshot.seq if snapshot else None,
            events_replayed=len(tail),
            warnings=warnings,
        )

        distance = target_seq - (snapshot.seq if snapshot else -1)
        has_checkpoint = any(event.event_type == "checkpoint.created" for event in tail)
        should_snapshot = force_snapshot or (
            target_seq == head_seq
            and (distance >= self.snapshot_interval or has_checkpoint)
        )
        if should_snapshot and state.cursor_seq >= 0:
            cursor_event = (
                tail[-1]
                if tail and tail[-1].clock.ingest_seq == state.cursor_seq
                else self.event_store.get_event(run_id, state.cursor_event_id or "")
            )
            event_hash = (
                cursor_event.integrity.event_hash
                if cursor_event and cursor_event.integrity
                else None
            )
            try:
                saved = self.snapshot_store.save(
                    WorldSnapshot.create(state, event_hash=event_hash)
                )
                result.snapshot_seq = saved.seq
            except SnapshotError as exc:
                result.warnings.append(f"snapshot not saved: {exc}")
        return result
