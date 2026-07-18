"""Agent Flow Visualizer - FastAPI Backend Server."""

import os
import sys
import subprocess
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from analyzer.ast_parser import parse_project
from analyzer.pattern_detector import detect_patterns
from analyzer.graph_builder import FlowGraph, build_graph, graph_to_dict
from tracer.tracer import trace_project_entry, trace_result_to_dict
from anthill import __version__
from anthill.api import EventBroker, create_anthill_router
from anthill.adapters import flow_graph_to_events, trace_result_to_events
from anthill.store import DuplicateEventError, JsonlEventStore


app = FastAPI(title="Agent Anthill", version=__version__)

# Local-first canonical event ledger. Set ANTHILL_DATA_DIR to keep recordings
# elsewhere; event content defaults to metadata-only when runtime traces are
# normalized into the ledger.
ANTHILL_DATA_DIR = Path(
    os.environ.get("ANTHILL_DATA_DIR", Path(__file__).parent / ".anthill-data")
).resolve()
event_store = JsonlEventStore(ANTHILL_DATA_DIR)
event_broker = EventBroker()
app.include_router(create_anthill_router(event_store, event_broker))

# Serve static files
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Analysis cache contains only pure analysis artifacts. Per-request persistence
# is deliberately applied after the cache lookup so cached reads cannot skip or
# leak side-effect metadata between requests.
_analysis_cache: dict[str, tuple[float, FlowGraph, dict]] = {}


class AnalyzeRequest(BaseModel):
    project_dir: str
    persist_events: bool = False
    run_id: str | None = None


class SimulateRequest(BaseModel):
    project_dir: str
    entry_point: str  # which entry function to start from
    input_data: dict  # simulated input


class TraceRequest(BaseModel):
    project_dir: str
    entry_module: str  # e.g., "sample_agent"
    entry_function: str  # e.g., "main"
    args: list = Field(default_factory=list)
    kwargs: dict = Field(default_factory=dict)
    run_id: str | None = None
    persist_events: bool = True
    capture_content: bool = False


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "anthill.html"))


@app.get("/anthill")
async def anthill_index():
    return FileResponse(str(STATIC_DIR / "anthill.html"))


@app.get("/graph")
async def graph_index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/browse")
async def browse_folder():
    """Open a native OS folder picker dialog via subprocess for reliability."""
    import asyncio

    def _pick():
        script = (
            "import tkinter as tk\n"
            "from tkinter import filedialog\n"
            "root = tk.Tk()\n"
            "root.withdraw()\n"
            "root.attributes('-topmost', True)\n"
            "root.focus_force()\n"
            "root.after(100, lambda: root.focus_force())\n"
            "p = filedialog.askdirectory(title='选择 Agent 项目目录')\n"
            "root.destroy()\n"
            "print(p or '', end='')\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return proc.stdout.strip()

    path = await asyncio.to_thread(_pick)
    return {"path": path}


@app.post("/api/analyze")
async def analyze_project(req: AnalyzeRequest):
    """Analyze a Python agent project and return the flow graph."""
    project_dir = os.path.abspath(req.project_dir)

    if not os.path.isdir(project_dir):
        raise HTTPException(status_code=400, detail=f"Directory not found: {project_dir}")

    # Check cache — invalidate if any .py file is newer
    cache_key = project_dir
    current_mtime = _get_project_mtime(project_dir)
    cached = _analysis_cache.get(cache_key)
    if cached is not None and cached[0] >= current_mtime:
        _cached_mtime, graph, cached_result = cached
        result = dict(cached_result)
    else:
        # Parse all Python files
        parse_results = parse_project(project_dir)

        if not parse_results:
            raise HTTPException(status_code=400, detail="No Python files found in the directory")

        # Collect parse errors
        parse_errors = []
        for _filepath, pr in parse_results.items():
            parse_errors.extend(pr.errors)

        # Detect agent patterns
        detection = detect_patterns(parse_results)

        # Build visualization graph
        graph = build_graph(parse_results, detection)
        gd = graph_to_dict(graph)

        # Warn about empty or very large graphs
        n_nodes = len(gd["nodes"])
        if n_nodes == 0:
            parse_errors.append("未检测到可分析的函数/类（可能不是 Python 项目）")
        elif n_nodes > 500:
            parse_errors.append(f"项目较大（{n_nodes} 节点），渲染可能较慢，建议聚焦子模块")

        result = {
            "success": True,
            "graph": gd,
            "project_dir": project_dir,
            "warnings": parse_errors,
        }
        _analysis_cache[cache_key] = (current_mtime, graph, dict(result))

    if req.persist_events:
        run_id = req.run_id or f"analysis_{uuid4().hex}"
        canonical = flow_graph_to_events(
            graph,
            run_id=run_id,
            project_id=Path(project_dir).name,
        )
        try:
            stored = event_store.append_many(canonical)
        except DuplicateEventError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        await event_broker.publish_many(stored)
        result["anthill"] = {
            "run_id": run_id,
            "event_count": len(stored),
            "first_seq": stored[0].clock.ingest_seq if stored else None,
            "last_seq": stored[-1].clock.ingest_seq if stored else None,
            "world_url": f"/api/anthill/runs/{run_id}/world",
        }

    return result


def _get_project_mtime(project_dir: str) -> float:
    """Get the most recent modification time of any .py file in the project."""
    latest = 0.0
    for root, dirs, files in os.walk(project_dir):
        # Skip common non-source directories
        dirs[:] = [
            d
            for d in dirs
            if d
            not in {
                "__pycache__",
                ".git",
                "node_modules",
                ".venv",
                "venv",
                ".tox",
                ".mypy_cache",
                "dist",
                "build",
                ".eggs",
            }
        ]
        for f in files:
            if f.endswith(".py"):
                try:
                    mt = os.path.getmtime(os.path.join(root, f))
                    if mt > latest:
                        latest = mt
                except OSError:
                    pass
    return latest


@app.post("/api/simulate")
async def simulate_flow(req: SimulateRequest):
    """Simulate data flow through the agent graph."""
    project_dir = os.path.abspath(req.project_dir)

    if not os.path.isdir(project_dir):
        raise HTTPException(status_code=400, detail=f"Directory not found: {project_dir}")

    parse_results = parse_project(project_dir)
    detection = detect_patterns(parse_results)
    graph = build_graph(parse_results, detection)

    # Build adjacency for traversal
    adjacency: dict[str, list[str]] = {}
    edge_map: dict[tuple[str, str], dict] = {}
    for edge in graph.edges:
        adjacency.setdefault(edge.source, []).append(edge.target)
        edge_map[(edge.source, edge.target)] = {
            "id": edge.id,
            "type": edge.edge_type,
            "label": edge.label,
        }

    # Find the entry point
    entry = req.entry_point
    node_ids = {n.id for n in graph.nodes}
    if entry not in node_ids:
        # Try to find by short name
        matches = [n.id for n in graph.nodes if n.label == entry or n.id.endswith(f".{entry}")]
        if matches:
            entry = matches[0]
        else:
            raise HTTPException(status_code=400, detail=f"Entry point not found: {req.entry_point}")

    # BFS traversal to simulate flow
    node_type_map = {n.id: n.node_type for n in graph.nodes}
    trace_steps = []
    visited = set()
    queue = [(entry, 0, req.input_data)]  # (node_id, step, current_data)

    while queue:
        node_id, step, data = queue.pop(0)
        if node_id in visited:
            continue
        visited.add(node_id)

        node_type = node_type_map.get(node_id, "process")

        # Simulate what happens at this node
        step_info = {
            "step": step,
            "node_id": node_id,
            "node_type": node_type,
            "input_data": _summarize_data(data),
            "output_data": _simulate_node_output(node_type, data),
            "edges_taken": [],
        }

        # Follow edges from this node
        targets = adjacency.get(node_id, [])
        for target in targets:
            if target not in visited:
                edge_info = edge_map.get((node_id, target), {})
                step_info["edges_taken"].append(
                    {
                        "target": target,
                        "edge_type": edge_info.get("type", "call"),
                        "condition": edge_info.get("label", ""),
                    }
                )
                queue.append((target, step + 1, step_info["output_data"]))

        trace_steps.append(step_info)

    return {
        "success": True,
        "trace": trace_steps,
        "entry_point": entry,
        "total_steps": len(trace_steps),
    }


def _summarize_data(data) -> dict:
    """Create a summary of the data at a node."""
    if isinstance(data, dict):
        return {k: str(v)[:100] for k, v in data.items()}
    return {"value": str(data)[:200]}


def _simulate_node_output(node_type: str, input_data: dict) -> dict:
    """Simulate what a node would output based on its type."""
    output = dict(input_data)

    if node_type == "entry_point":
        output["_stage"] = "initialized"
    elif node_type == "llm_call":
        output["_llm_response"] = "<LLM response based on input>"
        output["_stage"] = "llm_processed"
    elif node_type == "tool":
        output["_tool_result"] = "<tool execution result>"
        output["_stage"] = "tool_executed"
    elif node_type == "decision":
        output["_decision"] = "<branch selected based on conditions>"
        output["_stage"] = "routed"
    elif node_type == "sub_agent":
        output["_sub_result"] = "<sub-agent result>"
        output["_stage"] = "sub_agent_done"
    elif node_type == "output":
        output["_stage"] = "output_ready"
    else:
        output["_stage"] = "processed"

    return output


@app.post("/api/trace")
async def trace_execution(req: TraceRequest):
    """Trace real execution of a function and return recorded events."""
    project_dir = os.path.abspath(req.project_dir)

    if not os.path.isdir(project_dir):
        raise HTTPException(status_code=400, detail=f"Directory not found: {project_dir}")

    trace_result = trace_project_entry(
        project_dir=project_dir,
        entry_module=req.entry_module,
        entry_function=req.entry_function,
        args=req.args,
        kwargs=req.kwargs,
    )
    response = trace_result_to_dict(trace_result)

    if req.persist_events:
        # AST classifications enrich the trace but remain explicitly inferred;
        # the underlying function calls stay observed facts.
        parse_results = parse_project(project_dir)
        detection = detect_patterns(parse_results)
        run_id = req.run_id or f"run_{uuid4().hex}"
        canonical = trace_result_to_events(
            trace_result,
            run_id=run_id,
            project_id=Path(project_dir).name,
            classifications=detection.classifications,
            capture_content=req.capture_content,
        )
        try:
            stored = event_store.append_many(canonical)
        except DuplicateEventError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        await event_broker.publish_many(stored)
        response["anthill"] = {
            "run_id": run_id,
            "event_count": len(stored),
            "content_capture": "plaintext_opt_in" if req.capture_content else "metadata_only",
            "first_seq": stored[0].clock.ingest_seq if stored else None,
            "last_seq": stored[-1].clock.ingest_seq if stored else None,
            "world_url": f"/api/anthill/runs/{run_id}/world",
            "replay_url": f"/api/anthill/runs/{run_id}/replay",
            "stream_url": f"/api/anthill/runs/{run_id}/stream",
        }

    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765)
