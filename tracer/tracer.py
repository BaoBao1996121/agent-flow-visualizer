"""Runtime Tracer - Execute agent code and record actual execution traces.

Uses sys.settrace to monitor function calls, returns, and exceptions
during real execution. The trace can then be visualized alongside
the static analysis graph.
"""

import sys
import time
import importlib.util
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class TraceEvent:
    timestamp: float
    event_type: str  # "call", "return", "exception", "branch"
    function_name: str
    qualified_name: str  # module.Class.method
    filepath: str
    lineno: int
    args: dict = field(default_factory=dict)
    return_value: Optional[str] = None
    exception: Optional[str] = None
    duration_ms: Optional[float] = None


@dataclass
class TraceResult:
    events: list[TraceEvent] = field(default_factory=list)
    entry_point: str = ""
    total_duration_ms: float = 0.0
    error: Optional[str] = None
    success: bool = True


class AgentTracer:
    """Traces the execution of Python code using sys.settrace."""

    def __init__(self, project_dir: str, target_files: set[str] | None = None):
        self.project_dir = Path(project_dir).resolve()
        self.target_files = target_files  # Only trace these files; None = trace all in project
        self.events: list[TraceEvent] = []
        self._call_stack: list[tuple[str, float]] = []  # (qualified_name, start_time)
        self._active = False

    def _should_trace(self, filepath: str) -> bool:
        """Check if we should trace this file (only project files)."""
        if not filepath:
            return False
        try:
            fp = Path(filepath).resolve()
            # Must be under the project directory
            fp.relative_to(self.project_dir)
            if self.target_files:
                return any(fp.name == t or str(fp).endswith(t) for t in self.target_files)
            return True
        except (ValueError, OSError):
            return False

    def _get_qualified_name(self, frame) -> str:
        """Get qualified name from a frame (module.Class.method or module.function)."""
        code = frame.f_code
        func_name = code.co_name

        # Try to get class name from self/cls
        class_name = ""
        if "self" in frame.f_locals:
            class_name = type(frame.f_locals["self"]).__name__
        elif "cls" in frame.f_locals:
            cls = frame.f_locals["cls"]
            if isinstance(cls, type):
                class_name = cls.__name__

        # Get module name from filepath
        filepath = code.co_filename
        try:
            rel = Path(filepath).resolve().relative_to(self.project_dir)
            module = str(rel).replace("\\", "/")
            if module.endswith(".py"):
                module = module[:-3]
            module = module.replace("/", ".")
        except (ValueError, OSError):
            module = ""

        parts = [p for p in [module, class_name, func_name] if p]
        return ".".join(parts)

    def _safe_repr(self, obj: Any, max_len: int = 100) -> str:
        """Safely repr an object, truncating if needed."""
        try:
            r = repr(obj)
            if len(r) > max_len:
                return r[:max_len] + "..."
            return r
        except Exception:
            return "<repr failed>"

    def _trace_func(self, frame, event, arg):
        """The trace function called by sys.settrace."""
        if not self._active:
            return None

        filepath = frame.f_code.co_filename
        if not self._should_trace(filepath):
            return None

        now = time.perf_counter()
        qualified_name = self._get_qualified_name(frame)

        if event == "call":
            # Record function entry
            # Extract arguments
            args = {}
            code = frame.f_code
            argcount = code.co_argcount
            varnames = code.co_varnames[:argcount]
            for name in varnames:
                if name == "self":
                    continue
                if name in frame.f_locals:
                    args[name] = self._safe_repr(frame.f_locals[name])

            self.events.append(TraceEvent(
                timestamp=now,
                event_type="call",
                function_name=frame.f_code.co_name,
                qualified_name=qualified_name,
                filepath=str(Path(filepath).relative_to(self.project_dir)),
                lineno=frame.f_lineno,
                args=args,
            ))
            self._call_stack.append((qualified_name, now))

            return self._trace_func  # Continue tracing inside this function

        elif event == "return":
            duration_ms = None
            if self._call_stack and self._call_stack[-1][0] == qualified_name:
                _, start_time = self._call_stack.pop()
                duration_ms = (now - start_time) * 1000

            self.events.append(TraceEvent(
                timestamp=now,
                event_type="return",
                function_name=frame.f_code.co_name,
                qualified_name=qualified_name,
                filepath=str(Path(filepath).relative_to(self.project_dir)),
                lineno=frame.f_lineno,
                return_value=self._safe_repr(arg),
                duration_ms=duration_ms,
            ))

        elif event == "exception":
            exc_type, exc_value, _ = arg
            self.events.append(TraceEvent(
                timestamp=now,
                event_type="exception",
                function_name=frame.f_code.co_name,
                qualified_name=qualified_name,
                filepath=str(Path(filepath).relative_to(self.project_dir)),
                lineno=frame.f_lineno,
                exception=f"{exc_type.__name__}: {exc_value}",
            ))

        return self._trace_func

    def trace_function(self, func, *args, **kwargs) -> TraceResult:
        """Trace a specific function call."""
        result = TraceResult()
        result.entry_point = getattr(func, "__qualname__", str(func))

        self.events = []
        self._call_stack = []
        self._active = True

        start_time = time.perf_counter()
        old_trace = sys.gettrace()

        try:
            sys.settrace(self._trace_func)
            func(*args, **kwargs)
            result.success = True
        except Exception as e:
            result.error = f"{type(e).__name__}: {e}"
            result.success = False
        finally:
            sys.settrace(old_trace)
            self._active = False
            result.total_duration_ms = (time.perf_counter() - start_time) * 1000

        result.events = self.events
        return result


def trace_project_entry(
    project_dir: str,
    entry_module: str,
    entry_function: str,
    args: list | None = None,
    kwargs: dict | None = None,
) -> TraceResult:
    """Trace execution starting from a specific module function.

    Args:
        project_dir: Path to the project directory.
        entry_module: Module name relative to project (e.g., "sample_agent").
        entry_function: Function name to call (e.g., "main").
        args: Positional arguments to pass.
        kwargs: Keyword arguments to pass.

    Returns:
        TraceResult with all recorded events.
    """
    project_path = Path(project_dir).resolve()
    args = args or []
    kwargs = kwargs or {}

    # Add project dir to sys.path temporarily
    str_path = str(project_path)
    added_to_path = False
    if str_path not in sys.path:
        sys.path.insert(0, str_path)
        added_to_path = True

    result = TraceResult()

    try:
        # Import the module
        spec = importlib.util.spec_from_file_location(
            entry_module,
            str(project_path / entry_module.replace(".", "/")) + ".py",
        )
        if not spec or not spec.loader:
            # Try as package
            pkg_init = project_path / entry_module.replace(".", "/") / "__init__.py"
            if pkg_init.exists():
                spec = importlib.util.spec_from_file_location(
                    entry_module, str(pkg_init),
                    submodule_search_locations=[str(project_path / entry_module.replace(".", "/"))],
                )

        if not spec or not spec.loader:
            result.error = f"Cannot find module: {entry_module}"
            result.success = False
            return result

        module = importlib.util.module_from_spec(spec)
        sys.modules[entry_module] = module
        spec.loader.exec_module(module)

        # Find the function — support Class.method by auto-instantiating
        parts = entry_function.split(".")
        target = module
        instance = None  # Will hold auto-created class instance if needed

        for i, part in enumerate(parts):
            if not hasattr(target, part):
                result.error = f"Cannot find '{part}' in {target}"
                result.success = False
                return result
            target = getattr(target, part)

            # If this is a class and there are more parts (i.e., method name follows),
            # auto-instantiate the class so we can call the method on it
            if isinstance(target, type) and i < len(parts) - 1:
                try:
                    instance = target()
                    target = instance
                except Exception as e:
                    result.error = (
                        f"Cannot auto-instantiate {target.__name__}: "
                        f"{type(e).__name__}: {e}"
                    )
                    result.success = False
                    return result

        if not callable(target):
            result.error = f"{entry_function} is not callable"
            result.success = False
            return result

        # Trace
        tracer = AgentTracer(project_dir)
        result = tracer.trace_function(target, *args, **kwargs)

    except Exception as e:
        result.error = f"Trace setup failed: {type(e).__name__}: {e}\n{traceback.format_exc()}"
        result.success = False
    finally:
        if added_to_path and str_path in sys.path:
            sys.path.remove(str_path)
        # Clean up imported module
        sys.modules.pop(entry_module, None)

    return result


def trace_result_to_dict(result: TraceResult) -> dict:
    """Convert a TraceResult to a JSON-serializable dict."""
    return {
        "success": result.success,
        "error": result.error,
        "entry_point": result.entry_point,
        "total_duration_ms": round(result.total_duration_ms, 2),
        "event_count": len(result.events),
        "events": [
            {
                "timestamp": round(e.timestamp, 6),
                "event_type": e.event_type,
                "function_name": e.function_name,
                "qualified_name": e.qualified_name,
                "filepath": e.filepath,
                "lineno": e.lineno,
                "args": e.args,
                "return_value": e.return_value,
                "exception": e.exception,
                "duration_ms": round(e.duration_ms, 2) if e.duration_ms is not None else None,
            }
            for e in result.events
        ],
        # Build a simplified trace for visualization (only call events, in order)
        "call_sequence": [
            {
                "node_id": e.qualified_name,
                "function_name": e.function_name,
                "args": e.args,
                "lineno": e.lineno,
            }
            for e in result.events
            if e.event_type == "call"
        ],
    }
