"""Graph Builder - Convert analysis results into visualization graph data."""

from dataclasses import dataclass, field
from .ast_parser import ParseResult, FunctionInfo
from .pattern_detector import DetectionResult, NodeClassification


@dataclass
class GraphNode:
    id: str
    label: str
    node_type: str  # entry_point, llm_call, tool, decision, process, sub_agent, output, data_transform
    confidence: float
    reason: str
    filepath: str
    lineno: int
    source_code: str
    docstring: str
    parameters: list[str]
    decorators: list[str]
    has_branches: bool
    branch_count: int
    has_prompts: bool
    prompt_preview: str  # first prompt-like string
    is_async: bool
    class_name: str


@dataclass
class GraphEdge:
    id: str
    source: str  # node id
    target: str  # node id
    edge_type: str  # call, conditional_true, conditional_false, data_flow
    label: str
    condition: str  # for conditional edges


@dataclass
class FlowGraph:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def build_graph(
    parse_results: dict[str, ParseResult],
    detection: DetectionResult,
) -> FlowGraph:
    """Build a visualization graph from analysis results."""
    graph = FlowGraph()

    # Collect all functions
    all_functions: dict[str, FunctionInfo] = {}
    for pr in parse_results.values():
        all_functions.update(pr.functions)

    # Build name lookup for resolving calls
    # Maps various name forms -> list of qualified names
    name_lookup: dict[str, list[str]] = {}
    for qname in all_functions:
        parts = qname.split(".")
        # Full qualified name: module.Class.method
        name_lookup.setdefault(qname, []).append(qname)
        # Short name: just the function/method name
        short_name = parts[-1]
        name_lookup.setdefault(short_name, []).append(qname)
        # Class.method (without module prefix)
        if len(parts) >= 2:
            class_method = ".".join(parts[-2:])
            name_lookup.setdefault(class_method, []).append(qname)
        # For three-part names (module.Class.method), also map module.Class
        if len(parts) >= 3:
            no_method = ".".join(parts[:-1])
            name_lookup.setdefault(no_method, []).append(qname)

    # Create nodes
    node_ids = set()
    for qname, func in all_functions.items():
        classification = detection.classifications.get(qname)
        if not classification:
            classification = NodeClassification(
                node_type="process", confidence=0.2, reason="unclassified"
            )

        # Skip private helper methods with low confidence unless they're important
        if (
            func.name.startswith("_")
            and func.name != "__init__"
            and func.name != "__call__"
            and classification.confidence < 0.4
        ):
            continue

        prompt_preview = ""
        if func.string_literals:
            prompt_preview = func.string_literals[0][:150] + ("..." if len(func.string_literals[0]) > 150 else "")

        node = GraphNode(
            id=qname,
            label=f"{func.class_name}.{func.name}" if func.class_name else func.name,
            node_type=classification.node_type,
            confidence=classification.confidence,
            reason=classification.reason,
            filepath=func.filepath,
            lineno=func.lineno,
            source_code=func.source_code,
            docstring=func.docstring or "",
            parameters=func.parameters,
            decorators=func.decorators,
            has_branches=len(func.branches) > 0,
            branch_count=len(func.branches),
            has_prompts=len(func.string_literals) > 0,
            prompt_preview=prompt_preview,
            is_async=func.is_async,
            class_name=func.class_name or "",
        )
        graph.nodes.append(node)
        node_ids.add(qname)

    # Create edges
    edge_counter = 0
    seen_edges = set()

    for qname, func in all_functions.items():
        if qname not in node_ids:
            continue

        for call in func.calls:
            # Resolve call to a known function
            targets = _resolve_call(call, name_lookup, qname)
            for target in targets:
                if target not in node_ids or target == qname:
                    continue

                edge_key = (qname, target)
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)

                # Determine edge type using branch_call_map
                edge_type = "call"
                label = ""

                # Check if this specific call is inside a branch
                if func.branch_call_map:
                    # Try to find the call in the branch map
                    condition = func.branch_call_map.get(call, "")
                    if not condition:
                        # Try matching by short name
                        for map_call, map_cond in func.branch_call_map.items():
                            if map_call.split(".")[-1] == call.split(".")[-1]:
                                condition = map_cond
                                break
                    if condition:
                        edge_type = "conditional"
                        label = condition[:60]

                edge = GraphEdge(
                    id=f"e{edge_counter}",
                    source=qname,
                    target=target,
                    edge_type=edge_type,
                    label=label,
                    condition=label,
                )
                graph.edges.append(edge)
                edge_counter += 1

    # Add metadata
    graph.metadata = {
        "total_functions": len(all_functions),
        "displayed_nodes": len(graph.nodes),
        "displayed_edges": len(graph.edges),
        "detected_frameworks": list(detection.detected_frameworks),
        "entry_points": detection.entry_points,
        "llm_calls": detection.llm_calls,
        "tools": detection.tools,
        "decision_points": detection.decision_points,
        "sub_agents": detection.sub_agents,
    }

    return graph


def _resolve_call(call: str, name_lookup: dict[str, list[str]], caller: str) -> list[str]:
    """Resolve a call expression to known function qualified names."""

    # Common Python builtins/stdlib names — never resolve via ambiguous matching
    SKIP_SHORT_NAMES = {
        # container methods
        "append", "extend", "insert", "pop", "remove", "clear", "copy",
        "get", "set", "update", "items", "keys", "values", "setdefault",
        "add", "discard", "union", "intersection",
        # string methods
        "format", "join", "split", "strip", "replace", "lower", "upper",
        "startswith", "endswith", "encode", "decode",
        # logging
        "info", "error", "warning", "debug", "critical", "exception",
        # common stdlib
        "close", "read", "write", "seek", "flush", "send", "recv",
        "start", "stop", "run", "wait", "sleep", "cancel",
        "connect", "disconnect", "bind", "listen", "accept",
        "dumps", "loads", "dump", "load",
        # magic/dunder — always ambiguous via short name
        "__init__", "__call__", "__str__", "__repr__", "__len__",
        "__getitem__", "__setitem__", "__contains__", "__iter__",
        "__next__", "__enter__", "__exit__", "__del__", "__hash__",
        "__eq__", "__ne__", "__lt__", "__gt__", "__le__", "__ge__",
        "__bool__", "__getattr__", "__setattr__",
        # other very common names
        "execute", "process", "handle", "validate", "parse", "create",
        "delete", "save", "fetch", "request", "response", "to_dict",
        "from_dict", "to_json", "from_json", "configure", "initialize",
        "reset", "setUp", "tearDown", "test",
    }

    # Direct match (full qualified name)
    if call in name_lookup:
        candidates = name_lookup[call]
        # If this is a bare name (no dots) and it's a common method name,
        # it's likely a false match against all short-name entries
        if "." not in call and call in SKIP_SHORT_NAMES:
            return []
        # If it's a dotted name but the method part is a common name and
        # there are too many candidates, it's an ambiguous Class.method match
        last_part = call.rsplit(".", 1)[-1]
        if last_part in SKIP_SHORT_NAMES and len(candidates) > 3:
            return []
        return candidates

    parts = call.split(".")

    # Extract caller's full module path (everything before the class/function name)
    # e.g. "search_service.src.foo.bar.Cls.method"
    #   filepath-based module would be "search_service.src.foo.bar"
    caller_parts = caller.split(".")
    # The module is everything except the last 1-2 segments (class.method or just function)
    if len(caller_parts) >= 3:
        # Could be module.Class.method — module is everything up to -2
        caller_module = ".".join(caller_parts[:-2])
        caller_class = caller_parts[-2]
    elif len(caller_parts) == 2:
        caller_module = caller_parts[0]
        caller_class = ""
    else:
        caller_module = ""
        caller_class = ""

    def _prefer_same_scope(candidates: list[str]) -> list[str]:
        """From candidates, prefer same module > same top-level package > any.
        If still ambiguous (>3), return empty to avoid fan-out."""
        if not candidates:
            return []

        if caller_module:
            # Same module (exact)
            exact_mod = [c for c in candidates if c.startswith(caller_module + ".")]
            if exact_mod:
                if len(exact_mod) > 3:
                    return []  # ambiguous even within same module
                return exact_mod

            # Same top-level package
            top_pkg = caller_module.split(".")[0]
            same_pkg = [c for c in candidates if c.startswith(top_pkg + ".")]
            if same_pkg:
                # Still prefer same class within package
                if caller_class:
                    cls_match = [c for c in same_pkg if f".{caller_class}." in c]
                    if cls_match:
                        if len(cls_match) > 3:
                            return []
                        return cls_match
                if len(same_pkg) > 3:
                    return []  # too many candidates in same package
                return same_pkg

        # Same class name anywhere
        if caller_class:
            cls = [c for c in candidates if f".{caller_class}." in c]
            if cls:
                if len(cls) > 3:
                    return []
                return cls

        # Ambiguous fallback — limit to avoid fan-out
        if len(candidates) > 2:
            return []  # too ambiguous, skip
        return candidates

    # Handle "self.attr.method" pattern (e.g., self.faq_handler.handle)
    if parts[0] == "self" and len(parts) == 3:
        method_name = parts[2]
        if method_name in SKIP_SHORT_NAMES:
            return []
        attr_name = parts[1]
        if method_name in name_lookup:
            candidates = name_lookup[method_name]
            # Fuzzy match: "faq_handler" should match "FAQHandler"
            attr_normalized = attr_name.lower().replace("_", "")
            best = [c for c in candidates
                    if any(p.lower() == attr_normalized for p in c.split("."))]
            if best:
                return best
            # Partial match
            best = [c for c in candidates
                    if any(attr_normalized in p.lower() for p in c.split("."))]
            if best:
                return best
        return []

    # Try the last part (method name) — skip builtins
    short = parts[-1]
    if short in SKIP_SHORT_NAMES:
        return []

    if short in name_lookup:
        candidates = name_lookup[short]
        return _prefer_same_scope(candidates)

    # Try "self.method" pattern - resolve to class method
    if parts[0] == "self" and len(parts) == 2:
        method_name = parts[1]
        if method_name in SKIP_SHORT_NAMES:
            return []
        if method_name in name_lookup:
            candidates = name_lookup[method_name]
            return _prefer_same_scope(candidates)

    return []


def graph_to_dict(graph: FlowGraph) -> dict:
    """Convert graph to JSON-serializable dict."""
    return {
        "nodes": [
            {
                "id": n.id,
                "label": n.label,
                "type": n.node_type,
                "confidence": n.confidence,
                "reason": n.reason,
                "filepath": n.filepath,
                "lineno": n.lineno,
                "source_code": n.source_code,
                "docstring": n.docstring,
                "parameters": n.parameters,
                "decorators": n.decorators,
                "has_branches": n.has_branches,
                "branch_count": n.branch_count,
                "has_prompts": n.has_prompts,
                "prompt_preview": n.prompt_preview,
                "is_async": n.is_async,
                "class_name": n.class_name,
                "module_id": _filepath_to_group_id(n.filepath),
            }
            for n in graph.nodes
        ],
        "edges": [
            {
                "id": e.id,
                "source": e.source,
                "target": e.target,
                "type": e.edge_type,
                "label": e.label,
                "condition": e.condition,
            }
            for e in graph.edges
        ],
        "metadata": graph.metadata,
    }


def _filepath_to_group_id(filepath: str) -> str:
    """Convert filepath to a group ID for compound nodes.
    e.g. 'project_original\\milvus_build\\csv_api.py' → 'project_original/milvus_build/csv_api'
    """
    if not filepath:
        return "unknown"
    return filepath.replace("\\", "/").replace(".py", "").rstrip("/")
