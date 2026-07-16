"""AST Parser - Core static analysis for Python agent source code."""

import ast
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FunctionInfo:
    name: str
    qualified_name: str  # class.method or module.function
    filepath: str
    lineno: int
    end_lineno: int
    decorators: list[str] = field(default_factory=list)
    parameters: list[str] = field(default_factory=list)
    return_annotation: Optional[str] = None
    docstring: Optional[str] = None
    source_code: str = ""
    calls: list[str] = field(default_factory=list)  # functions this function calls
    string_literals: list[str] = field(default_factory=list)  # prompt templates etc.
    branches: list[dict] = field(default_factory=list)  # if/else/match branches
    branch_call_map: dict[str, str] = field(default_factory=dict)  # call_name -> branch condition
    is_async: bool = False
    class_name: Optional[str] = None


@dataclass
class ClassInfo:
    name: str
    filepath: str
    lineno: int
    end_lineno: int
    bases: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)  # method names
    docstring: Optional[str] = None


@dataclass
class ImportInfo:
    module: str
    names: list[str] = field(default_factory=list)
    alias: Optional[str] = None
    filepath: str = ""


@dataclass
class ParseResult:
    functions: dict[str, FunctionInfo] = field(default_factory=dict)
    classes: dict[str, ClassInfo] = field(default_factory=dict)
    imports: list[ImportInfo] = field(default_factory=list)
    global_calls: list[str] = field(default_factory=list)  # module-level calls
    module_variables: dict[str, str] = field(default_factory=dict)  # name -> type hint or value
    errors: list[str] = field(default_factory=list)  # parse errors


class CallExtractor(ast.NodeVisitor):
    """Extract all function/method calls from an AST node."""

    def __init__(self):
        self.calls: list[str] = []

    def visit_Call(self, node: ast.Call):
        call_name = self._get_call_name(node.func)
        if call_name:
            self.calls.append(call_name)
        self.generic_visit(node)

    def _get_call_name(self, node) -> Optional[str]:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            value = self._get_call_name(node.value)
            if value:
                return f"{value}.{node.attr}"
            return node.attr
        elif isinstance(node, ast.Subscript):
            return self._get_call_name(node.value)
        return None


class StringExtractor(ast.NodeVisitor):
    """Extract string literals (potential prompt templates)."""

    def __init__(self, min_length=30):
        self.strings: list[str] = []
        self.min_length = min_length

    def visit_Constant(self, node: ast.Constant):
        if isinstance(node.value, str) and len(node.value) >= self.min_length:
            self.strings.append(node.value)
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr):
        # f-strings
        parts = []
        for val in node.values:
            if isinstance(val, ast.Constant):
                parts.append(str(val.value))
            else:
                parts.append("{...}")
        joined = "".join(parts)
        if len(joined) >= self.min_length:
            self.strings.append(joined)
        self.generic_visit(node)


class BranchExtractor(ast.NodeVisitor):
    """Extract branching logic (if/else, match/case)."""

    def __init__(self):
        self.branches: list[dict] = []

    def visit_If(self, node: ast.If):
        branch = {
            "type": "if",
            "lineno": node.lineno,
            "condition": ast.unparse(node.test) if hasattr(ast, "unparse") else "...",
            "has_else": len(node.orelse) > 0,
            "elif_count": 0,
        }
        # Count elif chains
        current = node
        while current.orelse and len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
            branch["elif_count"] += 1
            current = current.orelse[0]
        self.branches.append(branch)
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match):
        branch = {
            "type": "match",
            "lineno": node.lineno,
            "subject": ast.unparse(node.subject) if hasattr(ast, "unparse") else "...",
            "case_count": len(node.cases),
        }
        self.branches.append(branch)
        self.generic_visit(node)


class BranchCallMapper(ast.NodeVisitor):
    """Map function calls to their containing branch conditions.

    For code like:
        if intent == "FAQ":
            return faq_handler.handle(...)
        elif intent == "COMPLAINT":
            return complaint_handler.handle(...)

    Produces: {"faq_handler.handle": 'intent == "FAQ"', "complaint_handler.handle": 'intent == "COMPLAINT"'}
    """

    def __init__(self):
        self.call_to_condition: dict[str, str] = {}

    def visit_If(self, node: ast.If):
        self._process_if_chain(node)

    def visit_Match(self, node: ast.Match):
        subject = ast.unparse(node.subject) if hasattr(ast, "unparse") else "..."
        for case_node in node.cases:
            pattern = ast.unparse(case_node.pattern) if hasattr(ast, "unparse") else "..."
            condition = f"{subject} == {pattern}"
            call_ext = CallExtractor()
            for stmt in case_node.body:
                call_ext.visit(stmt)
            for call in call_ext.calls:
                self.call_to_condition[call] = condition

    def _process_if_chain(self, node: ast.If):
        """Walk through an if/elif/else chain and map calls to conditions."""
        condition = ast.unparse(node.test) if hasattr(ast, "unparse") else "..."

        # Extract calls from the if body
        call_ext = CallExtractor()
        for stmt in node.body:
            call_ext.visit(stmt)
        for call in call_ext.calls:
            # Don't overwrite existing mappings (keep the more specific first match)
            if call not in self.call_to_condition:
                self.call_to_condition[call] = condition

        # Process elif / else
        if node.orelse:
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                # elif
                self._process_if_chain(node.orelse[0])
            else:
                # else block
                call_ext2 = CallExtractor()
                for stmt in node.orelse:
                    call_ext2.visit(stmt)
                for call in call_ext2.calls:
                    if call not in self.call_to_condition:
                        self.call_to_condition[call] = "else"


def _get_decorator_name(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        val = _get_decorator_name(node.value)
        return f"{val}.{node.attr}" if val else node.attr
    elif isinstance(node, ast.Call):
        return _get_decorator_name(node.func)
    return ""


def _get_base_name(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        val = _get_base_name(node.value)
        return f"{val}.{node.attr}" if val else node.attr
    elif isinstance(node, ast.Subscript):
        return _get_base_name(node.value)
    return ""


def parse_file(filepath: str, source: str) -> ParseResult:
    """Parse a single Python file and extract all relevant information."""
    result = ParseResult()

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        result.errors.append(f"{filepath}: SyntaxError at line {e.lineno}: {e.msg}")
        return result

    lines = source.splitlines()

    # Compute module prefix from filepath (e.g. "agents/router.py" -> "agents.router")
    module_prefix = _filepath_to_module(filepath)

    # Extract imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result.imports.append(ImportInfo(
                    module=alias.name,
                    names=[alias.name],
                    alias=alias.asname,
                    filepath=filepath,
                ))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                result.imports.append(ImportInfo(
                    module=node.module,
                    names=[a.name for a in (node.names or [])],
                    filepath=filepath,
                ))

    # Process top-level nodes
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_info = _extract_function(node, filepath, lines, None, module_prefix)
            result.functions[func_info.qualified_name] = func_info

        elif isinstance(node, ast.ClassDef):
            class_info = _extract_class(node, filepath, lines)
            result.classes[class_info.name] = class_info

            # Extract methods
            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_info = _extract_function(item, filepath, lines, node.name, module_prefix)
                    result.functions[func_info.qualified_name] = func_info

        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            extractor = CallExtractor()
            extractor.visit(node)
            result.global_calls.extend(extractor.calls)

        elif isinstance(node, ast.Assign):
            # Track module-level variable assignments
            for target in node.targets:
                if isinstance(target, ast.Name):
                    try:
                        val_repr = ast.unparse(node.value) if hasattr(ast, "unparse") else "..."
                        result.module_variables[target.id] = val_repr[:200]
                    except Exception:
                        pass

    return result


def _filepath_to_module(filepath: str) -> str:
    """Convert a filepath like 'agents/router.py' to module prefix 'agents.router'.
    For single-file projects, returns just the module name without extension.
    """
    # Normalize path separators
    fp = filepath.replace("\\", "/")
    # Remove .py extension
    if fp.endswith(".py"):
        fp = fp[:-3]
    # Remove __init__ suffix (package init)
    if fp.endswith("/__init__"):
        fp = fp[:-9]
    # Convert slashes to dots
    module = fp.replace("/", ".")
    # Remove leading dots
    module = module.lstrip(".")
    return module


def _extract_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    filepath: str,
    lines: list[str],
    class_name: Optional[str],
    module_prefix: str = "",
) -> FunctionInfo:
    # Build qualified name: module.Class.method or module.function
    # For single-module projects, skip the module prefix if it's just one file
    parts = []
    if module_prefix:
        parts.append(module_prefix)
    if class_name:
        parts.append(class_name)
    parts.append(node.name)
    qualified_name = ".".join(parts)

    # Get source code
    start = node.lineno - 1
    end = node.end_lineno if node.end_lineno else start + 1
    source = "\n".join(lines[start:end])

    # Decorators
    decorators = [_get_decorator_name(d) for d in node.decorator_list]

    # Parameters
    params = []
    for arg in node.args.args:
        if arg.arg != "self":
            params.append(arg.arg)

    # Return annotation
    ret_ann = None
    if node.returns:
        try:
            ret_ann = ast.unparse(node.returns) if hasattr(ast, "unparse") else None
        except Exception:
            pass

    # Docstring
    docstring = ast.get_docstring(node)

    # Extract calls
    call_extractor = CallExtractor()
    call_extractor.visit(node)

    # Extract strings (potential prompts)
    string_extractor = StringExtractor()
    string_extractor.visit(node)

    # Extract branches
    branch_extractor = BranchExtractor()
    branch_extractor.visit(node)

    # Extract branch-to-call mapping
    branch_call_mapper = BranchCallMapper()
    for stmt in ast.iter_child_nodes(node):
        if isinstance(stmt, (ast.If, ast.Match)):
            branch_call_mapper.visit(stmt)

    return FunctionInfo(
        name=node.name,
        qualified_name=qualified_name,
        filepath=filepath,
        lineno=node.lineno,
        end_lineno=end,
        decorators=decorators,
        parameters=params,
        return_annotation=ret_ann,
        docstring=docstring,
        source_code=source,
        calls=call_extractor.calls,
        string_literals=string_extractor.strings,
        branches=branch_extractor.branches,
        branch_call_map=branch_call_mapper.call_to_condition,
        is_async=isinstance(node, ast.AsyncFunctionDef),
        class_name=class_name,
    )


def _extract_class(node: ast.ClassDef, filepath: str, lines: list[str]) -> ClassInfo:
    bases = [_get_base_name(b) for b in node.bases]
    decorators = [_get_decorator_name(d) for d in node.decorator_list]
    methods = [
        item.name
        for item in ast.iter_child_nodes(node)
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    docstring = ast.get_docstring(node)

    return ClassInfo(
        name=node.name,
        filepath=filepath,
        lineno=node.lineno,
        end_lineno=node.end_lineno or node.lineno,
        bases=bases,
        decorators=decorators,
        methods=methods,
        docstring=docstring,
    )


def parse_project(project_dir: str) -> dict[str, ParseResult]:
    """Parse all Python files in a project directory."""
    results = {}

    for root, _dirs, files in os.walk(project_dir):
        # Skip common non-source directories
        rel_root = os.path.relpath(root, project_dir)
        skip_dirs = {".git", "__pycache__", ".venv", "venv", "node_modules", ".tox", "dist", "build", "egg-info"}
        if any(part in skip_dirs for part in rel_root.split(os.sep)):
            continue

        for fname in files:
            if not fname.endswith(".py"):
                continue

            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, project_dir)

            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    source = f.read()
                results[rel_path] = parse_file(rel_path, source)
            except (OSError, PermissionError):
                continue

    return results
