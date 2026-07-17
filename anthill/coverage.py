"""Truth-preserving instrumentation visibility projection.

The projection reports what the ledger contains and what registered adapters
are designed to observe. It intentionally does not turn missing events into an
absence claim or a synthetic percentage.
"""

from __future__ import annotations

from dataclasses import dataclass

from .projections.world import WorldState


COVERAGE_CONTRACT_VERSION = "0.2.0"

DOMAIN_ORDER = (
    "run",
    "agent",
    "task",
    "decision",
    "policy",
    "model",
    "tool",
    "retrieval",
    "embedding",
    "memory",
    "context",
    "compaction",
    "handoff",
    "checkpoint",
    "artifact",
    "human",
    "error",
    "usage",
    "cost",
    "budget",
    "guardrail",
    "evaluation",
    "code",
    "semantic",
    "telemetry",
    "manifest",
    "agui",
    "langgraph",
    "extension",
)


@dataclass(frozen=True)
class AdapterCoverageContract:
    label: str
    kind: str
    can_observe: tuple[str, ...]
    blind_spots: tuple[str, ...]


ADAPTER_CONTRACTS = {
    "anthill.demo.fixture": AdapterCoverageContract(
        label="Synthetic full-chamber exhibit",
        kind="synthetic",
        can_observe=(
            "run",
            "agent",
            "task",
            "decision",
            "policy",
            "model",
            "tool",
            "retrieval",
            "memory",
            "context",
            "compaction",
            "handoff",
            "checkpoint",
            "artifact",
            "error",
            "usage",
            "cost",
            "budget",
            "manifest",
        ),
        blind_spots=(
            "Synthetic declarations are not evidence from a real runtime.",
            "No model, network, tool, or external side effect is executed.",
        ),
    ),
    "anthill.python.ast": AdapterCoverageContract(
        label="Python static source adapter",
        kind="static",
        can_observe=("code", "semantic"),
        blind_spots=(
            "Static declarations do not prove an execution path ran.",
            "Dynamic imports, generated code, subprocesses, and remote internals are not observed.",
        ),
    ),
    "anthill.python.sys_settrace": AdapterCoverageContract(
        label="Python sys.settrace runtime adapter",
        kind="runtime",
        can_observe=("code", "semantic", "agent", "model", "tool", "retrieval", "error"),
        blind_spots=(
            "Subprocesses, other processes, native/GPU work, and remote model internals are not traced.",
            "Agent semantics inferred from code classification remain fallible.",
        ),
    ),
    "anthill.otlp-json": AdapterCoverageContract(
        label="OTLP JSON / OpenInference adapter",
        kind="mapped",
        can_observe=(
            "run",
            "agent",
            "model",
            "tool",
            "retrieval",
            "embedding",
            "guardrail",
            "evaluation",
            "context",
            "telemetry",
            "error",
            "usage",
            "cost",
        ),
        blind_spots=(
            "Only exported spans and attributes are visible; missing spans are not absence proof.",
            "Memory, compaction, checkpoint, and ownership details require explicit framework spans.",
        ),
    ),
    "anthill.ag-ui": AdapterCoverageContract(
        label="AG-UI event adapter",
        kind="mapped",
        can_observe=("run", "agent", "tool", "context", "error", "agui"),
        blind_spots=(
            "Standard AG-UI events do not identify model, retrieval, memory, or compaction internals.",
            "Metadata-only import preserves state structure but not private values.",
        ),
    ),
    "anthill.langgraph-v2": AdapterCoverageContract(
        label="LangGraph StreamPart v2 adapter",
        kind="mapped",
        can_observe=(
            "run",
            "agent",
            "model",
            "context",
            "checkpoint",
            "human",
            "error",
            "usage",
            "langgraph",
        ),
        blind_spots=(
            "Only requested StreamPart modes are visible; an omitted mode is not absence proof.",
            "Standard task parts identify graph nodes, not whether a node is specifically a tool, retrieval, or memory operation.",
            "State, message, task, checkpoint, and custom values remain metadata-only unless plaintext capture is explicitly enabled.",
            "Run completion is recorded only when the importer is explicitly told the captured stream is complete.",
        ),
    ),
    "anthill.branch.materializer": AdapterCoverageContract(
        label="Materialized branch provenance adapter",
        kind="materialized",
        can_observe=(),
        blind_spots=(
            "A materialized branch copies recorded history and adds no new runtime observation.",
            "Consult derived_from links and the parent run for original adapter coverage.",
        ),
    ),
}


def describe_adapter_contracts() -> dict[str, dict]:
    return {
        adapter: {
            "label": contract.label,
            "kind": contract.kind,
            "can_observe": list(contract.can_observe),
            "blind_spots": list(contract.blind_spots),
        }
        for adapter, contract in sorted(ADAPTER_CONTRACTS.items())
    }


def build_instrumentation_visibility(state: WorldState) -> dict:
    event_counts: dict[str, int] = {}
    extension_families: set[str] = set()
    for event_type, count in state.event_type_counts.items():
        prefix = event_type.split(".", 1)[0]
        domain = prefix if prefix in DOMAIN_ORDER else "extension"
        event_counts[domain] = event_counts.get(domain, 0) + count
        if domain == "extension":
            extension_families.add(prefix)

    measurement_keys = _measurement_domains(state.totals)
    observable: set[str] = set()
    adapter_rows = []
    unregistered = []
    blind_spots = []
    for adapter, count in sorted(state.source_adapters.items()):
        contract = ADAPTER_CONTRACTS.get(adapter)
        if contract is None:
            unregistered.append(adapter)
            adapter_rows.append(
                {
                    "adapter": adapter,
                    "event_count": count,
                    "registered": False,
                    "label": "Unregistered adapter",
                    "kind": "unknown",
                    "can_observe": [],
                    "blind_spots": ["No published capability contract; coverage remains unknown."],
                }
            )
            continue
        observable.update(contract.can_observe)
        blind_spots.extend(f"{contract.label}: {item}" for item in contract.blind_spots)
        adapter_rows.append(
            {
                "adapter": adapter,
                "event_count": count,
                "registered": True,
                "label": contract.label,
                "kind": contract.kind,
                "can_observe": list(contract.can_observe),
                "blind_spots": list(contract.blind_spots),
            }
        )

    domains = []
    for domain in DOMAIN_ORDER:
        count = event_counts.get(domain, 0)
        keys = measurement_keys.get(domain, [])
        status = (
            "observed"
            if count or keys
            else "observable_not_seen"
            if domain in observable
            else "outside_adapter_contract"
        )
        domains.append(
            {
                "domain": domain,
                "status": status,
                "event_count": count,
                "measurement_keys": keys,
            }
        )

    return {
        "contract_version": COVERAGE_CONTRACT_VERSION,
        "basis": "projected event vocabulary plus registered adapter capability contracts",
        "score": None,
        "domains": domains,
        "observed_domain_count": sum(row["status"] == "observed" for row in domains),
        "observable_domain_count": len(observable),
        "adapters": adapter_rows,
        "unregistered_adapters": unregistered,
        "blind_spots": sorted(set(blind_spots)),
        "unmapped_event_types": list(state.unknown_event_types),
        "extension_families": sorted(extension_families),
        "warnings": [
            "An observable domain with no event does not prove the operation did not happen.",
            "An observed domain proves event visibility, not complete instrumentation of that domain.",
            "No aggregate coverage score is emitted because adapter capabilities are not equivalent.",
        ],
    }


def _measurement_domains(totals: dict[str, int | float]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for key in sorted(totals):
        if key in {"input_tokens", "output_tokens", "cached_tokens", "total_tokens"}:
            result.setdefault("usage", []).append(key)
        elif key == "cost_usd":
            result.setdefault("cost", []).append(key)
    return result
