"""FastAPI surface for ingestion, inspection, streaming, and time travel."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import AsyncIterator, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field

from .adapters.agui import (
    AguiImportError,
    agui_json_to_events,
    agui_ndjson_to_events,
)
from .adapters.langgraph import (
    LangGraphImportError,
    langgraph_ndjson_to_events,
    langgraph_v2_to_events,
)
from .adapters.otlp import OtlpImportError, otlp_json_to_events
from .branching import materialize_fork_events
from .coverage import (
    COVERAGE_CONTRACT_VERSION,
    build_instrumentation_visibility,
    describe_adapter_contracts,
)
from .projection_service import WorldProjectionService
from .projections import (
    REDUCER_VERSION,
    build_causal_slice,
    compare_runs,
    project_world,
)
from .projections.world import ZONE_BY_FAMILY
from .demo import build_demo_events
from .schema import (
    SCHEMA_VERSION,
    AgentRuntimeEvent,
    CoreEventType,
    EvidenceLevel,
    SourceFidelity,
)
from .snapshots import JsonWorldSnapshotStore, calculate_state_hash
from .store import DuplicateEventError, JsonlEventStore


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PrivacySafeValidationRoute(APIRoute):
    """Return useful 422s without reflecting rejected request values."""

    def get_route_handler(self):
        original_route_handler = super().get_route_handler()

        async def privacy_safe_route_handler(request: Request):
            try:
                return await original_route_handler(request)
            except RequestValidationError as exc:
                details = []
                for error in exc.errors():
                    location = error.get("loc", ())
                    scope = location[0] if location else "request"
                    if scope not in {"body", "query", "path", "header", "cookie"}:
                        scope = "request"
                    error_type = error.get("type", "value_error")
                    if not isinstance(error_type, str) or not error_type.isascii():
                        error_type = "value_error"
                    details.append(
                        {
                            "type": error_type[:128],
                            "loc": [scope],
                            "msg": "Request validation failed",
                        }
                    )
                return JSONResponse(status_code=422, content={"detail": details})

        return privacy_safe_route_handler


class IngestEventsRequest(ApiModel):
    events: list[AgentRuntimeEvent] = Field(min_length=1, max_length=10_000)


class OtlpImportRequest(ApiModel):
    payload: dict
    run_id: str | None = Field(default=None, min_length=1, max_length=256)
    semantic_convention_version: str | None = Field(default=None, max_length=64)
    capture_content: bool = False


class AguiImportRequest(ApiModel):
    payload: dict | list[dict] | str
    format: Literal["json", "ndjson"] = "json"
    run_id: str | None = Field(default=None, min_length=1, max_length=256)
    protocol_version: str | None = Field(default=None, max_length=64)
    capture_content: bool = False


class LangGraphImportRequest(ApiModel):
    payload: dict | list[dict] | str
    format: Literal["json", "ndjson"] = "json"
    run_id: str | None = Field(default=None, min_length=1, max_length=256)
    thread_id: str | None = Field(default=None, min_length=1, max_length=256)
    framework_version: str | None = Field(default=None, max_length=64)
    stream_complete: bool | None = None
    run_status: Literal["completed", "success", "failed", "interrupted", "cancelled"] | None = None
    capture_content: bool = False


class ForkRunRequest(ApiModel):
    at_seq: int | None = Field(default=None, ge=0)
    new_run_id: str | None = Field(default=None, min_length=1, max_length=256)
    title: str | None = Field(default=None, min_length=1, max_length=240)


class EventBroker:
    """Best-effort in-process wake-up channel; the ledger remains authoritative."""

    def __init__(self, *, queue_size: int = 2_000):
        self.queue_size = queue_size
        self._lock = asyncio.Lock()
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)

    async def subscribe(self, run_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=self.queue_size)
        async with self._lock:
            self._subscribers[run_id].add(queue)
        return queue

    async def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        async with self._lock:
            subscribers = self._subscribers.get(run_id)
            if subscribers is None:
                return
            subscribers.discard(queue)
            if not subscribers:
                self._subscribers.pop(run_id, None)

    async def publish_many(self, events: list[AgentRuntimeEvent]) -> None:
        if not events:
            return
        run_id = events[0].run_id
        async with self._lock:
            subscribers = list(self._subscribers.get(run_id, ()))
        for event in events:
            for queue in subscribers:
                if queue.full():
                    # Dropping the oldest notification is safe because the SSE
                    # consumer detects the sequence gap and resyncs from JSONL.
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    pass


def create_anthill_router(
    store: JsonlEventStore,
    broker: EventBroker,
) -> APIRouter:
    router = APIRouter(
        prefix="/api/anthill",
        tags=["Agent Anthill"],
        route_class=PrivacySafeValidationRoute,
    )
    snapshot_store = JsonWorldSnapshotStore(store.root / "_snapshots")
    projection_service = WorldProjectionService(store, snapshot_store)

    @router.get("/schema")
    async def describe_schema():
        return {
            "schema_version": SCHEMA_VERSION,
            "reducer_version": REDUCER_VERSION,
            "event_types": [item.value for item in CoreEventType],
            "evidence_levels": [item.value for item in EvidenceLevel],
            "source_fidelities": [item.value for item in SourceFidelity],
            "zone_by_family": ZONE_BY_FAMILY,
            "coverage_contract_version": COVERAGE_CONTRACT_VERSION,
            "adapter_coverage_contracts": describe_adapter_contracts(),
            "truth_contract": {
                "observed": "Captured directly while the runtime executed",
                "declared": "Explicitly present in source or framework configuration",
                "inferred": "A fallible semantic interpretation with confidence below 1",
                "counterfactual_verified": "Validated through a recorded intervention and rerun",
            },
        }

    @router.get("/runs")
    async def list_runs(
        limit: int = Query(default=100, ge=1, le=1_000),
        offset: int = Query(default=0, ge=0),
    ):
        manifests = store.list_runs()
        return {
            "total": len(manifests),
            "offset": offset,
            "limit": limit,
            "items": manifests[offset : offset + limit],
        }

    @router.get("/compare")
    async def compare_run_pair(
        left_run_id: str = Query(min_length=1, max_length=256),
        right_run_id: str = Query(min_length=1, max_length=256),
        progress: float = Query(default=1.0, ge=0.0, le=1.0),
    ):
        if left_run_id == right_run_id:
            raise HTTPException(status_code=422, detail="choose two different runs")
        left = list(store.read_run(left_run_id))
        right = list(store.read_run(right_run_id))
        missing = [
            run_id for run_id, events in ((left_run_id, left), (right_run_id, right)) if not events
        ]
        if missing:
            raise HTTPException(
                status_code=404,
                detail={"message": "run not found", "run_ids": missing},
            )
        return compare_runs(
            left,
            right,
            left_run_id=left_run_id,
            right_run_id=right_run_id,
            progress=progress,
        )

    @router.post("/demo", status_code=201)
    async def create_demo():
        run_id = f"demo_{uuid4().hex}"
        stored = store.append_many(build_demo_events(run_id))
        await broker.publish_many(stored)
        return {
            "run_id": run_id,
            "event_count": len(stored),
            "synthetic": True,
            "world_url": f"/api/anthill/runs/{run_id}/world",
        }

    @router.post("/import/otlp", status_code=201)
    async def import_otlp(body: OtlpImportRequest):
        run_id = body.run_id or f"otlp_{uuid4().hex}"
        try:
            canonical = otlp_json_to_events(
                body.payload,
                run_id=run_id,
                semantic_convention_version=body.semantic_convention_version,
                capture_content=body.capture_content,
            )
            stored = store.append_many(canonical)
        except OtlpImportError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except DuplicateEventError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        await broker.publish_many(stored)
        return {
            "run_id": run_id,
            "event_count": len(stored),
            "span_count": max((len(stored) - 3) // 2, 0),
            "content_capture": ("plaintext_opt_in" if body.capture_content else "metadata_only"),
            "world_url": f"/api/anthill/runs/{run_id}/world",
        }

    @router.post("/import/agui", status_code=201)
    async def import_agui(body: AguiImportRequest):
        try:
            if body.format == "ndjson":
                if not isinstance(body.payload, str):
                    raise AguiImportError("NDJSON import payload must be a string")
                canonical = agui_ndjson_to_events(
                    body.payload,
                    run_id=body.run_id,
                    protocol_version=body.protocol_version,
                    capture_content=body.capture_content,
                )
            else:
                if not isinstance(body.payload, (dict, list)):
                    raise AguiImportError("JSON import payload must be an object or array")
                canonical = agui_json_to_events(
                    body.payload,
                    run_id=body.run_id,
                    protocol_version=body.protocol_version,
                    capture_content=body.capture_content,
                )
            stored = store.append_many(canonical)
        except AguiImportError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except DuplicateEventError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        effective_run_id = canonical[0].run_id
        await broker.publish_many(stored)
        return {
            "run_id": effective_run_id,
            "event_count": len(stored),
            "source_format": body.format,
            "protocol_version": canonical[0].source.semantic_convention_version,
            "content_capture": ("plaintext_opt_in" if body.capture_content else "metadata_only"),
            "world_url": f"/api/anthill/runs/{effective_run_id}/world",
        }

    @router.post("/import/langgraph", status_code=201)
    async def import_langgraph(body: LangGraphImportRequest):
        try:
            if body.format == "ndjson":
                if not isinstance(body.payload, str):
                    raise LangGraphImportError("NDJSON import payload must be a string")
                if body.run_id is None:
                    raise LangGraphImportError("run_id is required for NDJSON import")
                canonical = langgraph_ndjson_to_events(
                    body.payload,
                    run_id=body.run_id,
                    thread_id=body.thread_id,
                    framework_version=body.framework_version,
                    stream_complete=bool(body.stream_complete),
                    run_status=body.run_status,
                    capture_content=body.capture_content,
                )
            else:
                if not isinstance(body.payload, (dict, list)):
                    raise LangGraphImportError(
                        "JSON import payload must be a StreamPart object, array, or envelope"
                    )
                canonical = langgraph_v2_to_events(
                    body.payload,
                    run_id=body.run_id,
                    thread_id=body.thread_id,
                    framework_version=body.framework_version,
                    stream_complete=body.stream_complete,
                    run_status=body.run_status,
                    capture_content=body.capture_content,
                )
            stored = store.append_many(canonical)
        except LangGraphImportError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except DuplicateEventError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        effective_run_id = canonical[0].run_id
        terminal_event = next(
            (event for event in reversed(stored) if event.event_type == "run.completed"),
            None,
        )
        await broker.publish_many(stored)
        return {
            "run_id": effective_run_id,
            "event_count": len(stored),
            "source_format": body.format,
            "stream_version": canonical[0].source.semantic_convention_version,
            "stream_complete": terminal_event is not None,
            "run_status": (terminal_event.payload.get("status") if terminal_event else None),
            "content_capture": ("plaintext_opt_in" if body.capture_content else "metadata_only"),
            "world_url": f"/api/anthill/runs/{effective_run_id}/world",
        }

    @router.post("/runs/{run_id}/events", status_code=201)
    async def ingest_events(run_id: str, body: IngestEventsRequest):
        mismatched = [event.event_id for event in body.events if event.run_id != run_id]
        if mismatched:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "all event run_id values must match the URL",
                    "event_ids": mismatched[:20],
                },
            )
        try:
            stored = store.append_many(body.events)
        except DuplicateEventError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        await broker.publish_many(stored)
        return {
            "run_id": run_id,
            "accepted": len(stored),
            "first_seq": stored[0].clock.ingest_seq,
            "last_seq": stored[-1].clock.ingest_seq,
            "event_ids": [event.event_id for event in stored],
        }

    @router.post("/runs/{run_id}/fork", status_code=201)
    async def fork_run(run_id: str, body: ForkRunRequest):
        projection = projection_service.project(run_id, at_seq=body.at_seq)
        if projection is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        new_run_id = body.new_run_id or f"fork_{uuid4().hex}"
        if new_run_id == run_id:
            raise HTTPException(status_code=422, detail="new_run_id must differ from parent")
        if _run_exists(store, new_run_id):
            raise HTTPException(status_code=409, detail=f"run already exists: {new_run_id}")
        parent_events = list(store.read_run(run_id, to_seq=projection.target_seq))
        canonical = materialize_fork_events(
            parent_events,
            parent_run_id=run_id,
            new_run_id=new_run_id,
            parent_state_hash=calculate_state_hash(projection.state),
            title=body.title,
        )
        stored = store.append_many(canonical)
        await broker.publish_many(stored)
        return {
            "run_id": new_run_id,
            "parent_run_id": run_id,
            "parent_seq": projection.target_seq,
            "parent_event_id": projection.state.cursor_event_id,
            "event_count": len(stored),
            "side_effects_replayed": False,
            "world_url": f"/api/anthill/runs/{new_run_id}/world",
        }

    @router.get("/runs/{run_id}/events")
    async def query_events(
        run_id: str,
        from_seq: int = Query(default=0, ge=0),
        to_seq: int | None = Query(default=None, ge=0),
        event_type: list[str] | None = Query(default=None),
        limit: int = Query(default=500, ge=1, le=5_000),
    ):
        if to_seq is not None and to_seq < from_seq:
            raise HTTPException(status_code=422, detail="to_seq cannot be below from_seq")
        iterator = store.read_run(
            run_id,
            from_seq=from_seq,
            to_seq=to_seq,
            event_types=event_type,
        )
        items = []
        has_more = False
        for item in iterator:
            if len(items) >= limit:
                has_more = True
                break
            items.append(item)
        if not items and not _run_exists(store, run_id):
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        return {
            "run_id": run_id,
            "from_seq": from_seq,
            "to_seq": to_seq,
            "count": len(items),
            "has_more": has_more,
            "next_seq": ((items[-1].clock.ingest_seq or 0) + 1 if items and has_more else None),
            "items": [item.model_dump(mode="json") for item in items],
        }

    @router.get("/runs/{run_id}/events/{event_id}")
    async def get_event(run_id: str, event_id: str):
        event = store.get_event(run_id, event_id)
        if event is None:
            raise HTTPException(status_code=404, detail=f"event not found: {event_id}")
        return event.model_dump(mode="json")

    @router.get("/runs/{run_id}/world")
    async def get_world(
        run_id: str,
        at_seq: int | None = Query(default=None, ge=0),
    ):
        result = projection_service.project(run_id, at_seq=at_seq)
        if result is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        state = result.state
        return {
            "run_id": run_id,
            "requested_seq": at_seq,
            "projected_seq": state.cursor_seq,
            "head_seq": result.head_seq,
            "is_head": at_seq is None or state.cursor_seq == result.head_seq,
            "projection": {
                "reducer_version": state.reducer_version,
                "snapshot_seq": result.snapshot_seq,
                "events_replayed": result.events_replayed,
                "warnings": result.warnings,
            },
            "visibility": build_instrumentation_visibility(state),
            "state": state.model_dump(mode="json"),
        }

    @router.post("/runs/{run_id}/snapshots", status_code=201)
    async def create_world_snapshot(run_id: str):
        result = projection_service.project(run_id, force_snapshot=True)
        if result is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        return {
            "run_id": run_id,
            "seq": result.snapshot_seq,
            "reducer_version": result.state.reducer_version,
            "events_replayed": result.events_replayed,
            "warnings": result.warnings,
        }

    @router.get("/runs/{run_id}/snapshots")
    async def list_world_snapshots(run_id: str):
        if not _run_exists(store, run_id):
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        items = snapshot_store.list_run(run_id)
        return {"run_id": run_id, "count": len(items), "items": items}

    @router.get("/runs/{run_id}/replay")
    async def get_replay_window(
        run_id: str,
        from_seq: int = Query(default=0, ge=0),
        to_seq: int | None = Query(default=None, ge=0),
        limit: int = Query(default=2_000, ge=1, le=5_000),
    ):
        all_events = list(store.read_run(run_id))
        if not all_events:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        if to_seq is not None and to_seq < from_seq:
            raise HTTPException(status_code=422, detail="to_seq cannot be below from_seq")

        initial = project_world(
            all_events,
            run_id=run_id,
            at_seq=from_seq - 1,
        )
        selected = [
            event
            for event in all_events
            if (event.clock.ingest_seq or 0) >= from_seq
            and (to_seq is None or (event.clock.ingest_seq or 0) <= to_seq)
        ]
        truncated = len(selected) > limit
        selected = selected[:limit]
        final = project_world(
            selected,
            run_id=run_id,
            initial_state=initial,
        )
        return {
            "run_id": run_id,
            "from_seq": from_seq,
            "to_seq": to_seq,
            "truncated": truncated,
            "next_seq": (
                (selected[-1].clock.ingest_seq or 0) + 1 if truncated and selected else None
            ),
            "initial_state": initial.model_dump(mode="json"),
            "events": [event.model_dump(mode="json") for event in selected],
            "final_state": final.model_dump(mode="json"),
        }

    @router.get("/runs/{run_id}/causal/{event_id}")
    async def get_causal_slice(
        run_id: str,
        event_id: str,
        direction: str = Query(default="both", pattern="^(ancestors|descendants|both)$"),
        max_depth: int = Query(default=12, ge=0, le=100),
    ):
        events = list(store.read_run(run_id))
        if not events:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        try:
            return build_causal_slice(
                events,
                event_id=event_id,
                direction=direction,
                max_depth=max_depth,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"event not found: {event_id}") from exc

    @router.get("/runs/{run_id}/integrity")
    async def verify_integrity(run_id: str):
        result = store.verify_run(run_id)
        if result["event_count"] == 0 and not _run_exists(store, run_id):
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        return result

    @router.get("/runs/{run_id}/stream")
    async def stream_run(
        request: Request,
        run_id: str,
        after_seq: int = Query(default=-1, ge=-1),
    ):
        if not _run_exists(store, run_id):
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")

        async def stream() -> AsyncIterator[str]:
            queue = await broker.subscribe(run_id)
            cursor = after_seq
            try:
                # Subscribe before reading backlog. Duplicate notifications are
                # removed by the sequence cursor, so no event can fall in the gap.
                for event in store.read_run(run_id, from_seq=after_seq + 1):
                    if await request.is_disconnected():
                        return
                    if event.clock.ingest_seq is not None:
                        cursor = event.clock.ingest_seq
                    yield _sse_event(event)

                while not await request.is_disconnected():
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    except asyncio.TimeoutError:
                        yield ": heartbeat\n\n"
                        continue
                    seq = event.clock.ingest_seq
                    if seq is None or seq <= cursor:
                        continue
                    if seq > cursor + 1:
                        gap = {
                            "expected_seq": cursor + 1,
                            "observed_seq": seq,
                            "resync_from": cursor + 1,
                        }
                        yield f"event: gap\ndata: {json.dumps(gap)}\n\n"
                        for missed in store.read_run(
                            run_id,
                            from_seq=cursor + 1,
                            to_seq=seq - 1,
                        ):
                            if missed.clock.ingest_seq is not None:
                                cursor = missed.clock.ingest_seq
                            yield _sse_event(missed)
                    cursor = seq
                    yield _sse_event(event)
            finally:
                await broker.unsubscribe(run_id, queue)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return router


def _run_exists(store: JsonlEventStore, run_id: str) -> bool:
    return store.get_manifest(run_id) is not None


def _sse_event(event: AgentRuntimeEvent) -> str:
    seq = event.clock.ingest_seq
    return f"id: {seq}\nevent: runtime-event\ndata: {event.model_dump_json()}\n\n"
