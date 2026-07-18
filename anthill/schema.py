"""Versioned canonical event schema for Agent Anthill.

The schema deliberately separates what happened from how it will be drawn.  A
renderer can turn a tool call into a worker entering a workshop, but the stored
fact remains a tool call with an explicit source, evidence level, and causal
links.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator


SCHEMA_VERSION = "0.2.0"
_EVENT_TYPE_RE = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$")
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def new_event_id() -> str:
    """Return an opaque event identifier.

    Ordering never depends on the identifier; ``clock.ingest_seq`` is the
    authoritative append order.  This keeps imported IDs and local IDs equally
    valid.
    """

    return f"evt_{uuid4().hex}"


def is_visibly_stable_run_id(value: str) -> bool:
    """Return whether a run ID is safe to expose as an unescaped identity key."""

    return value == value.strip() and not any(
        unicodedata.category(character) in {"Cc", "Cf"} for character in value
    )


def is_addressable_run_id(value: str) -> bool:
    """Return whether a run ID is one stable HTTP path segment."""

    reserved = {"/", "\\", "?", "#", "%"}
    return is_visibly_stable_run_id(value) and value not in {".", ".."} and not any(
        character in reserved for character in value
    )


class EvidenceLevel(str, Enum):
    """How strongly the system can claim that an event is true."""

    OBSERVED = "observed"
    DECLARED = "declared"
    INFERRED = "inferred"
    COUNTERFACTUAL_VERIFIED = "counterfactual_verified"


class SourceFidelity(str, Enum):
    """How directly an adapter obtained an event."""

    NATIVE = "native"
    MAPPED = "mapped"
    INFERRED = "inferred"


class ContentCapture(str, Enum):
    """Persistence policy for potentially sensitive event content."""

    METADATA_ONLY = "metadata_only"
    REDACTED = "redacted"
    PLAINTEXT_OPT_IN = "plaintext_opt_in"
    ENCRYPTED = "encrypted"


class LinkType(str, Enum):
    CAUSED_BY = "caused_by"
    FOLLOWS_FROM = "follows_from"
    SPAWNED_BY = "spawned_by"
    DELEGATED_BY = "delegated_by"
    RETRIEVED_FROM = "retrieved_from"
    REPLACED_BY = "replaced_by"
    DERIVED_FROM = "derived_from"
    RELATED = "related"


class CoreEventType(str, Enum):
    """Stable core vocabulary.

    ``AgentRuntimeEvent.event_type`` remains an open string so adapters may add
    namespaced extensions without waiting for a core release.
    """

    RUN_STARTED = "run.started"
    RUN_PAUSED = "run.paused"
    RUN_RESUMED = "run.resumed"
    RUN_FORKED = "run.forked"
    RUN_COMPLETED = "run.completed"
    RUN_CANCELLED = "run.cancelled"

    AGENT_SPAWNED = "agent.spawned"
    AGENT_STATE_CHANGED = "agent.state.changed"
    AGENT_PLAN_CREATED = "agent.plan.created"
    AGENT_STEP_STARTED = "agent.step.started"
    AGENT_STEP_COMPLETED = "agent.step.completed"

    TASK_CREATED = "task.created"
    TASK_STATE_CHANGED = "task.state.changed"

    MODEL_REQUEST_PREPARED = "model.request.prepared"
    MODEL_REQUEST_DISPATCHED = "model.request.dispatched"
    MODEL_RESPONSE_FIRST_CHUNK = "model.response.first_chunk"
    MODEL_RESPONSE_CHUNK = "model.response.chunk"
    MODEL_RESPONSE_COMPLETED = "model.response.completed"
    MODEL_CACHE_HIT = "model.cache.hit"
    MODEL_CACHE_MISS = "model.cache.miss"
    MODEL_RETRY = "model.retry"
    MODEL_FALLBACK = "model.fallback"
    MODEL_FAILED = "model.failed"

    TOOL_CALL_REQUESTED = "tool.call.requested"
    TOOL_ARGS_DELTA = "tool.args.delta"
    TOOL_APPROVAL_REQUESTED = "tool.approval.requested"
    TOOL_APPROVAL_GRANTED = "tool.approval.granted"
    TOOL_APPROVAL_REJECTED = "tool.approval.rejected"
    TOOL_EXECUTION_STARTED = "tool.execution.started"
    TOOL_EXECUTION_PROGRESS = "tool.execution.progress"
    TOOL_EXECUTION_SUCCEEDED = "tool.execution.succeeded"
    TOOL_EXECUTION_FAILED = "tool.execution.failed"
    TOOL_RETRY_SCHEDULED = "tool.retry.scheduled"
    TOOL_SIDE_EFFECT_COMMITTED = "tool.side_effect.committed"

    RETRIEVAL_QUERY_CREATED = "retrieval.query.created"
    RETRIEVAL_QUERY_REWRITTEN = "retrieval.query.rewritten"
    RETRIEVAL_SEARCH_STARTED = "retrieval.search.started"
    RETRIEVAL_SEARCH_COMPLETED = "retrieval.search.completed"
    RETRIEVAL_CANDIDATES_RETURNED = "retrieval.candidates.returned"
    RETRIEVAL_RERANK_COMPLETED = "retrieval.rerank.completed"
    RETRIEVAL_DOCUMENTS_SELECTED = "retrieval.documents.selected"

    MEMORY_SEARCHED = "memory.searched"
    MEMORY_READ = "memory.read"
    MEMORY_HIT = "memory.hit"
    MEMORY_MISS = "memory.miss"
    MEMORY_WRITTEN = "memory.written"
    MEMORY_UPDATED = "memory.updated"
    MEMORY_DELETED = "memory.deleted"
    MEMORY_CONSOLIDATED = "memory.consolidated"
    MEMORY_DECAYED = "memory.decayed"
    MEMORY_EVICTED = "memory.evicted"
    MEMORY_CONFLICT_DETECTED = "memory.conflict.detected"

    CONTEXT_ASSEMBLY_STARTED = "context.assembly.started"
    CONTEXT_ITEM_ADDED = "context.item.added"
    CONTEXT_ITEM_REMOVED = "context.item.removed"
    CONTEXT_ITEM_TRUNCATED = "context.item.truncated"
    CONTEXT_BUDGET_UPDATED = "context.budget.updated"
    CONTEXT_OVERFLOW_DETECTED = "context.overflow.detected"
    CONTEXT_POLICY_APPLIED = "context.policy.applied"
    CONTEXT_ASSEMBLY_COMPLETED = "context.assembly.completed"

    COMPACTION_TRIGGERED = "compaction.triggered"
    COMPACTION_STARTED = "compaction.started"
    COMPACTION_SUMMARY_CREATED = "compaction.summary.created"
    COMPACTION_ITEMS_REPLACED = "compaction.items.replaced"
    COMPACTION_COMPLETED = "compaction.completed"
    COMPACTION_FAILED = "compaction.failed"

    HANDOFF_PROPOSED = "handoff.proposed"
    HANDOFF_ACCEPTED = "handoff.accepted"
    HANDOFF_REJECTED = "handoff.rejected"
    HANDOFF_STARTED = "handoff.started"
    HANDOFF_COMPLETED = "handoff.completed"

    CHECKPOINT_CREATED = "checkpoint.created"
    CHECKPOINT_RESTORED = "checkpoint.restored"
    CHECKPOINT_FORKED = "checkpoint.forked"
    CHECKPOINT_COMMITTED = "checkpoint.committed"
    CHECKPOINT_INVALIDATED = "checkpoint.invalidated"

    ARTIFACT_CREATED = "artifact.created"
    ARTIFACT_UPDATED = "artifact.updated"
    HUMAN_INTERRUPT = "human.interrupt"
    HUMAN_FEEDBACK = "human.feedback"

    ERROR_RAISED = "error.raised"
    ERROR_CAUGHT = "error.caught"
    ERROR_RETRY = "error.retry"
    ERROR_RECOVERED = "error.recovered"
    ERROR_FATAL = "error.fatal"
    ERROR_TIMEOUT = "error.timeout"
    ERROR_CANCELLED = "error.cancelled"

    USAGE_MEASURED = "usage.measured"
    COST_CALCULATED = "cost.calculated"
    BUDGET_WARNING = "budget.warning"
    BUDGET_EXHAUSTED = "budget.exhausted"
    MANIFEST_SNAPSHOT = "manifest.snapshot"
    POLICY_CHANGED = "policy.changed"

    CODE_ENTITY_DECLARED = "code.entity.declared"
    CODE_RELATION_DECLARED = "code.relation.declared"
    CODE_CALL_STARTED = "code.call.started"
    CODE_CALL_RETURNED = "code.call.returned"
    CODE_CALL_RAISED = "code.call.raised"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class EventClock(StrictModel):
    occurred_at: datetime = Field(default_factory=utc_now)
    observed_at: datetime = Field(default_factory=utc_now)
    monotonic_ns: int | None = Field(default=None, ge=0)
    source_seq: int | None = Field(default=None, ge=0)
    ingest_seq: int | None = Field(default=None, ge=0)

    @field_validator("occurred_at", "observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("event timestamps must be timezone-aware")
        return value


class EventSource(StrictModel):
    adapter: str = Field(min_length=1, max_length=160)
    adapter_version: str = Field(default="0.1.0", min_length=1, max_length=64)
    framework: str | None = Field(default=None, max_length=100)
    framework_version: str | None = Field(default=None, max_length=64)
    language: str | None = Field(default=None, max_length=40)
    fidelity: SourceFidelity
    semantic_convention: str | None = Field(default=None, max_length=120)
    semantic_convention_version: str | None = Field(default=None, max_length=64)
    raw_event_ref: str | None = Field(default=None, max_length=2048)


class EvidenceRef(StrictModel):
    kind: str = Field(min_length=1, max_length=80)
    uri: str = Field(min_length=1, max_length=2048)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    label: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def line_range_is_ordered(self) -> "EvidenceRef":
        if self.line_start and self.line_end and self.line_end < self.line_start:
            raise ValueError("line_end must be greater than or equal to line_start")
        return self


class Evidence(StrictModel):
    level: EvidenceLevel
    confidence: float = Field(ge=0.0, le=1.0)
    refs: list[EvidenceRef] = Field(default_factory=list)
    derived_from: list[str] = Field(default_factory=list)
    explanation: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def inference_cannot_claim_certainty(self) -> "Evidence":
        if self.level == EvidenceLevel.INFERRED and self.confidence >= 1.0:
            raise ValueError("inferred evidence cannot have confidence 1.0")
        return self


class EntityRef(StrictModel):
    kind: str = Field(min_length=1, max_length=80)
    id: str = Field(min_length=1, max_length=256)
    name: str | None = Field(default=None, max_length=240)
    parent_id: str | None = Field(default=None, max_length=256)
    attributes: dict[str, Any] = Field(default_factory=dict)


class EventLink(StrictModel):
    type: LinkType | str
    event_id: str | None = Field(default=None, max_length=256)
    run_id: str | None = Field(default=None, max_length=256)
    trace_id: str | None = Field(default=None, max_length=256)
    span_id: str | None = Field(default=None, max_length=256)
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def has_target(self) -> "EventLink":
        if not any((self.event_id, self.run_id, self.trace_id, self.span_id)):
            raise ValueError("an event link must identify at least one target")
        return self


class ArtifactRef(StrictModel):
    uri: str = Field(min_length=1, max_length=2048)
    mime_type: str | None = Field(default=None, max_length=200)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    size_bytes: int | None = Field(default=None, ge=0)
    role: str | None = Field(default=None, max_length=80)


class Privacy(StrictModel):
    content: ContentCapture = ContentCapture.METADATA_ONLY
    contains_sensitive_data: bool = False
    redacted_fields: list[str] = Field(default_factory=list)
    retention_days: int | None = Field(default=None, ge=0)


class EventIntegrity(StrictModel):
    algorithm: str = "sha256"
    previous_event_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    event_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class AgentRuntimeEvent(StrictModel):
    """Canonical, renderer-independent event envelope."""

    schema_version: str = SCHEMA_VERSION
    event_id: str = Field(default_factory=new_event_id, min_length=1, max_length=256)
    event_type: str

    run_id: str = Field(min_length=1, max_length=256)
    thread_id: str | None = Field(default=None, max_length=256)
    session_id: str | None = Field(default=None, max_length=256)
    project_id: str | None = Field(default=None, max_length=256)
    task_id: str | None = Field(default=None, max_length=256)
    agent_id: str | None = Field(default=None, max_length=256)

    trace_id: str | None = Field(default=None, max_length=256)
    span_id: str | None = Field(default=None, max_length=256)
    parent_span_id: str | None = Field(default=None, max_length=256)
    causation_id: str | None = Field(default=None, max_length=256)
    correlation_id: str | None = Field(default=None, max_length=256)
    links: list[EventLink] = Field(default_factory=list)

    clock: EventClock = Field(default_factory=EventClock)
    source: EventSource
    subject: EntityRef | None = None
    evidence: Evidence

    summary: str | None = Field(default=None, max_length=1000)
    payload: dict[str, Any] = Field(default_factory=dict)
    measurements: dict[str, int | float | str | bool | None] = Field(default_factory=dict)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    privacy: Privacy = Field(default_factory=Privacy)
    extensions: dict[str, Any] = Field(default_factory=dict)
    integrity: EventIntegrity | None = None

    @field_validator("schema_version")
    @classmethod
    def valid_schema_version(cls, value: str) -> str:
        if not _SEMVER_RE.fullmatch(value):
            raise ValueError("schema_version must be semantic version text")
        return value

    @field_validator("event_type", mode="before")
    @classmethod
    def valid_event_type(cls, value: CoreEventType | str) -> str:
        normalized = value.value if isinstance(value, CoreEventType) else str(value)
        normalized = normalized.strip().lower()
        if not _EVENT_TYPE_RE.fullmatch(normalized):
            raise ValueError("event_type must be a lowercase, namespaced identifier")
        return normalized

    @model_validator(mode="after")
    def new_ingest_run_id_is_visibly_stable(self, info: ValidationInfo) -> "AgentRuntimeEvent":
        context = info.context or {}
        legacy_storage_read = (
            self.schema_version == "0.1.0"
            and bool(context.get("allow_legacy_run_id"))
        )
        if legacy_storage_read:
            return self
        if self.run_id != self.run_id.strip():
            raise ValueError("run_id cannot contain leading or trailing whitespace")
        if any(unicodedata.category(character) in {"Cc", "Cf"} for character in self.run_id):
            raise ValueError("run_id cannot contain control or format characters")
        if not is_addressable_run_id(self.run_id):
            raise ValueError("run_id must be one addressable API path segment")
        return self

    @model_validator(mode="after")
    def causal_links_cannot_point_to_self(self) -> "AgentRuntimeEvent":
        if self.causation_id == self.event_id:
            raise ValueError("an event cannot cause itself")
        if any(link.event_id == self.event_id for link in self.links):
            raise ValueError("an event link cannot target itself")
        return self

    def with_ingest_metadata(
        self,
        *,
        ingest_seq: int,
        previous_event_hash: str | None,
        observed_at: datetime | None = None,
    ) -> "AgentRuntimeEvent":
        """Return a store-stamped copy with a tamper-evident hash chain."""

        clock = self.clock.model_copy(
            update={"ingest_seq": ingest_seq, "observed_at": observed_at or utc_now()}
        )
        unhashed = self.model_copy(
            update={
                "clock": clock,
                "integrity": EventIntegrity(previous_event_hash=previous_event_hash),
            }
        )
        event_hash = unhashed.calculate_hash()
        return unhashed.model_copy(
            update={
                "integrity": EventIntegrity(
                    previous_event_hash=previous_event_hash,
                    event_hash=event_hash,
                )
            }
        )

    def calculate_hash(self) -> str:
        """Calculate the canonical event hash, excluding ``event_hash`` itself."""

        data = self.model_dump(mode="json")
        integrity = data.get("integrity") or {
            "algorithm": "sha256",
            "previous_event_hash": None,
            "event_hash": None,
        }
        integrity["event_hash"] = None
        data["integrity"] = integrity
        canonical = json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def to_json_line(self) -> str:
        return self.model_dump_json(exclude_none=False) + "\n"
