"""Pattern Detector - Identify agent-specific patterns in parsed code."""

from dataclasses import dataclass, field
from .ast_parser import ParseResult, FunctionInfo, ImportInfo


# Known LLM/Agent framework patterns
LLM_CALL_PATTERNS = {
    # OpenAI
    "openai", "ChatCompletion", "chat.completions.create", "client.chat.completions.create",
    "completions.create", "client.completions.create",
    # Anthropic
    "anthropic", "messages.create", "client.messages.create",
    # LangChain
    "ChatOpenAI", "ChatAnthropic", "LLMChain", "invoke", "ainvoke",
    "chain.run", "chain.invoke", "llm.invoke", "llm.predict",
    # Generic
    "generate", "complete", "chat",
}

TOOL_DECORATOR_PATTERNS = {
    "tool", "function_tool", "register_tool",
    "langchain.tools.tool", "crewai.tool",
}

AGENT_CLASS_PATTERNS = {
    "Agent", "BaseAgent", "AgentExecutor", "CrewAgent",
    "AssistantAgent", "UserProxyAgent", "ConversableAgent",
}

AGENT_FRAMEWORK_MODULES = {
    "langchain", "langgraph", "openai", "anthropic",
    "autogen", "crewai", "llama_index", "smolagents",
    "swarm", "pydantic_ai",
}


@dataclass
class NodeClassification:
    node_type: str  # entry_point, llm_call, tool, decision, process, sub_agent, output, data_transform
    confidence: float  # 0.0 - 1.0
    reason: str
    framework: str = ""  # detected framework


@dataclass
class DetectionResult:
    classifications: dict[str, NodeClassification] = field(default_factory=dict)  # qualified_name -> classification
    detected_frameworks: set[str] = field(default_factory=set)
    entry_points: list[str] = field(default_factory=list)
    llm_calls: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    decision_points: list[str] = field(default_factory=list)
    sub_agents: list[str] = field(default_factory=list)


def detect_frameworks(imports: list[ImportInfo]) -> set[str]:
    """Detect which agent frameworks are used based on imports."""
    frameworks = set()
    for imp in imports:
        module_root = imp.module.split(".")[0]
        if module_root in AGENT_FRAMEWORK_MODULES:
            frameworks.add(module_root)
        for name in imp.names:
            name_root = name.split(".")[0]
            if name_root in AGENT_FRAMEWORK_MODULES:
                frameworks.add(name_root)
    return frameworks


def classify_function(func: FunctionInfo, frameworks: set[str], all_functions: dict[str, FunctionInfo]) -> NodeClassification:
    """Classify a function based on its characteristics."""
    scores = {
        "entry_point": 0.0,
        "llm_call": 0.0,
        "tool": 0.0,
        "decision": 0.0,
        "process": 0.0,
        "sub_agent": 0.0,
        "output": 0.0,
        "data_transform": 0.0,
    }
    reasons = []

    # --- Entry point detection ---
    if func.name in ("main", "run", "execute", "start", "__call__", "handle", "process_request"):
        scores["entry_point"] += 0.6
        reasons.append(f"entry-like name '{func.name}'")
    if func.name == "__call__":
        scores["entry_point"] += 0.3
        reasons.append("__call__ method")
    if not func.class_name and func.name == "main":
        scores["entry_point"] += 0.4
        reasons.append("top-level main function")
    # Functions that are called by no other analyzed function (potential entry)
    # Build a set of all "short" callable names that appear in any function's calls
    func_short = func.name
    func_class_method = f"{func.class_name}.{func.name}" if func.class_name else func.name
    called_by_others = False
    for other_name, other in all_functions.items():
        if other_name == func.qualified_name:
            continue
        for call in other.calls:
            # Normalize the call: "self.xxx.method" -> check method, "self.method" -> check method
            call_parts = call.split(".")
            call_tail = call_parts[-1]
            # Check if this call could refer to our function
            if call_tail == func_short:
                # Additional check: if it's self.attr.method, verify attr matches class
                if call_parts[0] == "self" and len(call_parts) == 3 and func.class_name:
                    attr_norm = call_parts[1].lower().replace("_", "")
                    class_norm = func.class_name.lower()
                    if attr_norm in class_norm or class_norm in attr_norm:
                        called_by_others = True
                        break
                elif call_parts[0] == "self" and len(call_parts) == 2:
                    # self.method -> same class
                    if other.class_name and func.class_name and other.class_name == func.class_name:
                        called_by_others = True
                        break
                else:
                    # Direct call or attribute call
                    called_by_others = True
                    break
            elif call == func.qualified_name or call == func_class_method:
                called_by_others = True
                break
        if called_by_others:
            break
    if not called_by_others and not func.name.startswith("_"):
        scores["entry_point"] += 0.2
        reasons.append("not called by other functions")

    # --- LLM call detection ---
    for call in func.calls:
        call_lower = call.lower()
        # Check against the defined LLM_CALL_PATTERNS set
        if any(pattern.lower() in call_lower for pattern in LLM_CALL_PATTERNS):
            # High confidence for specific API patterns
            if any(p.lower() in call_lower for p in [
                "completions.create", "messages.create", "chat.completions",
                "llm.invoke", "llm.predict", "chain.invoke", "chain.run",
                "llm.generate", "model.invoke", "model.generate", "ainvoke",
            ]):
                scores["llm_call"] += 0.9
                reasons.append(f"LLM API call: {call}")
            else:
                scores["llm_call"] += 0.4
                reasons.append(f"LLM-related call: {call}")

    # Check for prompt templates in string literals
    if func.string_literals:
        for s in func.string_literals:
            s_lower = s.lower()
            if any(kw in s_lower for kw in ["you are", "system:", "user:", "assistant:", "prompt", "instruction"]):
                scores["llm_call"] += 0.3
                reasons.append("contains prompt-like string")
                break

    # --- Tool detection ---
    for dec in func.decorators:
        dec_lower = dec.lower()
        # Check against TOOL_DECORATOR_PATTERNS
        if any(p.lower() in dec_lower for p in TOOL_DECORATOR_PATTERNS):
            scores["tool"] += 0.9
            reasons.append(f"tool decorator: @{dec}")
    if func.docstring and func.name not in ("__init__", "__call__"):
        if any(kw in func.name.lower() for kw in ["search", "fetch", "query", "lookup", "get_", "send_", "create_", "delete_", "update_"]):
            scores["tool"] += 0.3
            reasons.append(f"tool-like name: {func.name}")

    # --- Class-based agent detection ---
    if func.class_name and func.class_name in AGENT_CLASS_PATTERNS:
        if func.name in ("run", "execute", "__call__", "invoke"):
            scores["entry_point"] += 0.5
            reasons.append(f"method of agent class {func.class_name}")
        elif func.name not in ("__init__",):
            scores["sub_agent"] += 0.3
            reasons.append(f"member of agent class {func.class_name}")

    # --- Decision point detection ---
    if func.branches:
        branch_count = len(func.branches)
        if branch_count >= 2:
            scores["decision"] += 0.5
            reasons.append(f"{branch_count} branch points")
        elif branch_count == 1:
            scores["decision"] += 0.2

        # Check if branches follow LLM calls (routing based on LLM output)
        if scores["llm_call"] > 0.3 and branch_count > 0:
            scores["decision"] += 0.4
            reasons.append("branches after LLM calls (routing)")

        # Match statements suggest routing
        for b in func.branches:
            if b["type"] == "match":
                scores["decision"] += 0.5
                reasons.append("match/case routing")

    # --- Sub-agent detection ---
    for call in func.calls:
        call_lower = call.lower()
        if any(kw in call_lower for kw in ["agent.run", "agent.execute", "agent.invoke", "crew.kickoff"]):
            scores["sub_agent"] += 0.8
            reasons.append(f"sub-agent call: {call}")
        elif "agent" in call_lower and any(kw in call_lower for kw in [".run", ".execute", ".invoke", ".start"]):
            scores["sub_agent"] += 0.5
            reasons.append(f"possible sub-agent: {call}")

    # --- Output detection ---
    if func.name in ("format_response", "format_output", "send_response", "return_result", "output"):
        scores["output"] += 0.7
        reasons.append(f"output-like name: {func.name}")
    if func.return_annotation and "response" in func.return_annotation.lower():
        scores["output"] += 0.3
        reasons.append("returns response type")

    # --- Data transform detection ---
    if func.name in ("parse", "transform", "convert", "format", "serialize", "deserialize", "extract", "clean"):
        scores["data_transform"] += 0.5
        reasons.append(f"transform-like name: {func.name}")

    # Pick the highest scoring type
    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]

    # Default to 'process' if nothing stands out
    if best_score < 0.2:
        best_type = "process"
        best_score = 0.3
        reasons.append("generic process node")

    return NodeClassification(
        node_type=best_type,
        confidence=min(best_score, 1.0),
        reason="; ".join(reasons[:5]),
        framework=next(iter(frameworks), ""),
    )


def detect_patterns(parse_results: dict[str, ParseResult]) -> DetectionResult:
    """Analyze all parse results and detect agent patterns."""
    result = DetectionResult()

    # Collect all imports and detect frameworks
    all_imports = []
    for pr in parse_results.values():
        all_imports.extend(pr.imports)
    result.detected_frameworks = detect_frameworks(all_imports)

    # Collect all functions
    all_functions: dict[str, FunctionInfo] = {}
    for pr in parse_results.values():
        all_functions.update(pr.functions)

    # Classify each function
    for name, func in all_functions.items():
        classification = classify_function(func, result.detected_frameworks, all_functions)
        result.classifications[name] = classification

        if classification.node_type == "entry_point":
            result.entry_points.append(name)
        elif classification.node_type == "llm_call":
            result.llm_calls.append(name)
        elif classification.node_type == "tool":
            result.tools.append(name)
        elif classification.node_type == "decision":
            result.decision_points.append(name)
        elif classification.node_type == "sub_agent":
            result.sub_agents.append(name)

    # If no entry points found, pick the function that calls the most other classified functions
    if not result.entry_points and all_functions:
        best_entry = None
        best_count = 0
        for name, func in all_functions.items():
            if func.name.startswith("_"):
                continue
            call_count = sum(
                1 for c in func.calls
                if any(c == fn or c == fn.split(".")[-1] for fn in all_functions)
            )
            if call_count > best_count:
                best_count = call_count
                best_entry = name
        if best_entry:
            result.entry_points.append(best_entry)
            result.classifications[best_entry] = NodeClassification(
                node_type="entry_point",
                confidence=0.4,
                reason="calls most other functions (inferred entry point)",
            )

    return result
