"""OmniTools Coding Intelligence Engine - Dependency & Test Target Analysis

Provides AST-based static dependency graphs, third-party package extraction,
standard library classification, reverse dependent mapping, and targeted test selection.
Cross-platform compatible across Windows, Linux, and macOS.
"""

from __future__ import annotations

import ast
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Standard library module names (Python 3.10+ native frozenset)
_STDLIB_MODULES: frozenset[str] = getattr(
    sys, "stdlib_module_names", frozenset()
).union(sys.builtin_module_names)


@dataclass
class ImportSummary:
    """Summary of imports extracted from a single Python file."""

    file_path: str
    internal_imports: list[str] = field(default_factory=list)
    external_dependencies: list[str] = field(default_factory=list)
    standard_library: list[str] = field(default_factory=list)
    raw_imports: list[str] = field(default_factory=list)
    syntax_error: Optional[str] = None


@dataclass
class WorkspaceGraph:
    """Full workspace dependency and reverse dependent graph."""

    root_dir: str
    forward_graph: dict[str, list[str]] = field(default_factory=dict)
    reverse_graph: dict[str, list[str]] = field(default_factory=dict)
    file_summaries: dict[str, ImportSummary] = field(default_factory=dict)
    all_files: list[str] = field(default_factory=list)


def _normalize_path(path: Union[str, Path], relative_to: Optional[Union[str, Path]] = None) -> str:
    """Normalize path to POSIX forward slashes relative to workspace root."""
    p = Path(path).resolve()
    if relative_to:
        root = Path(relative_to).resolve()
        try:
            return p.relative_to(root).as_posix()
        except ValueError:
            pass
    return p.as_posix()


def is_test_file(path_str: str) -> bool:
    """Determine whether a given file path is a test file."""
    norm = path_str.replace("\\", "/").lower()
    name = Path(norm).name
    if name.startswith("test_") and name.endswith(".py"):
        return True
    if name.endswith("_test.py"):
        return True
    parts = norm.split("/")
    if "tests" in parts or "test" in parts:
        if name.endswith(".py") and not name.startswith("__"):
            return True
    return False


def resolve_import_path(
    module_name: Optional[str],
    current_file: Path,
    workspace_root: Path,
    level: int = 0,
    subname: Optional[str] = None,
) -> Optional[str]:
    """Resolve Python module name to a workspace relative file path if internal."""
    workspace_root = workspace_root.resolve()
    current_file = current_file.resolve()

    # 1. Handle relative imports (from . import x or from ..x import y)
    if level > 0:
        base_dir = current_file.parent
        for _ in range(level - 1):
            base_dir = base_dir.parent

        if module_name:
            rel_parts = module_name.split(".")
            candidate_file = base_dir.joinpath(*rel_parts).with_suffix(".py")
            candidate_init = base_dir.joinpath(*rel_parts).joinpath("__init__.py")
        else:
            candidate_file = base_dir.with_suffix(".py")
            candidate_init = base_dir.joinpath("__init__.py")

        if candidate_file.is_file():
            return _normalize_path(candidate_file, workspace_root)
        if candidate_init.is_file():
            if subname:
                sub_file = candidate_init.parent.joinpath(subname).with_suffix(".py")
                if sub_file.is_file():
                    return _normalize_path(sub_file, workspace_root)
            return _normalize_path(candidate_init, workspace_root)

        # Check if subname is a submodule in base_dir when module_name is None
        if not module_name and subname:
            sub_file = base_dir.joinpath(subname).with_suffix(".py")
            sub_init = base_dir.joinpath(subname, "__init__.py")
            if sub_file.is_file():
                return _normalize_path(sub_file, workspace_root)
            if sub_init.is_file():
                return _normalize_path(sub_init, workspace_root)

        return None

    if not module_name:
        return None

    parts = module_name.split(".")

    # 2. Check candidate directly from workspace root
    cand1_file = workspace_root.joinpath(*parts).with_suffix(".py")
    cand1_init = workspace_root.joinpath(*parts).joinpath("__init__.py")
    if cand1_file.is_file():
        return _normalize_path(cand1_file, workspace_root)
    if cand1_init.is_file():
        if subname:
            sub_file = cand1_init.parent.joinpath(subname).with_suffix(".py")
            if sub_file.is_file():
                return _normalize_path(sub_file, workspace_root)
        return _normalize_path(cand1_init, workspace_root)

    # 3. Check candidate in src directory if not already starting with src
    if parts[0] != "src":
        cand2_file = workspace_root.joinpath("src", *parts).with_suffix(".py")
        cand2_init = workspace_root.joinpath("src", *parts).joinpath("__init__.py")
        if cand2_file.is_file():
            return _normalize_path(cand2_file, workspace_root)
        if cand2_init.is_file():
            if subname:
                sub_file = cand2_init.parent.joinpath(subname).with_suffix(".py")
                if sub_file.is_file():
                    return _normalize_path(sub_file, workspace_root)
            return _normalize_path(cand2_init, workspace_root)

    # 4. Check if subname forms the file: e.g. from src.core import tools
    if subname:
        cand3_file = workspace_root.joinpath(*parts, subname).with_suffix(".py")
        cand3_init = workspace_root.joinpath(*parts, subname, "__init__.py")
        if cand3_file.is_file():
            return _normalize_path(cand3_file, workspace_root)
        if cand3_init.is_file():
            return _normalize_path(cand3_init, workspace_root)

        if parts[0] != "src":
            cand4_file = workspace_root.joinpath("src", *parts, subname).with_suffix(".py")
            cand4_init = workspace_root.joinpath("src", *parts, subname, "__init__.py")
            if cand4_file.is_file():
                return _normalize_path(cand4_file, workspace_root)
            if cand4_init.is_file():
                return _normalize_path(cand4_init, workspace_root)

    return None


def extract_imports(
    file_path: Union[str, Path],
    workspace_root: Optional[Union[str, Path]] = None,
) -> ImportSummary:
    """Extract AST imports from a single Python file."""
    fpath = Path(file_path).resolve()
    wroot = Path(workspace_root).resolve() if workspace_root else fpath.parent
    rel_path = _normalize_path(fpath, wroot)

    summary = ImportSummary(file_path=rel_path)

    if not fpath.is_file():
        summary.syntax_error = f"File not found: {fpath}"
        return summary

    try:
        content = fpath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(content, filename=str(fpath))
    except Exception as exc:
        summary.syntax_error = f"AST parse error: {str(exc)}"
        return summary

    raw_imports_list: list[str] = []
    internal_set: set[str] = set()
    external_set: set[str] = set()
    stdlib_set: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                raw_imports_list.append(alias.name)
                top_level = alias.name.split(".")[0]
                resolved = resolve_import_path(alias.name, fpath, wroot, level=0)
                if resolved:
                    internal_set.add(resolved)
                elif top_level in _STDLIB_MODULES:
                    stdlib_set.add(top_level)
                else:
                    external_set.add(top_level)

        elif isinstance(node, ast.ImportFrom):
            mod = node.module
            level = node.level
            prefix = "." * level + (mod or "")
            raw_imports_list.append(prefix)

            # Check if base module resolves to internal file
            resolved_base = resolve_import_path(mod, fpath, wroot, level=level)
            if resolved_base:
                internal_set.add(resolved_base)

            # Check if any imported symbol resolves to an internal submodule
            for alias in node.names:
                resolved_sub = resolve_import_path(mod, fpath, wroot, level=level, subname=alias.name)
                if resolved_sub:
                    internal_set.add(resolved_sub)

            if not resolved_base and level == 0 and mod:
                top_level = mod.split(".")[0]
                if top_level in _STDLIB_MODULES:
                    stdlib_set.add(top_level)
                else:
                    external_set.add(top_level)

    # Discard self-import if present
    internal_set.discard(rel_path)

    summary.internal_imports = sorted(internal_set)
    summary.external_dependencies = sorted(external_set)
    summary.standard_library = sorted(stdlib_set)
    summary.raw_imports = sorted(set(raw_imports_list))

    return summary


def build_workspace_dependency_graph(
    workspace_root: Optional[Union[str, Path]] = None,
    exclude_dirs: Optional[set[str]] = None,
) -> WorkspaceGraph:
    """Scan and index dependency relationships across the entire workspace."""
    wroot = Path(workspace_root or Path.cwd()).resolve()
    excluded = exclude_dirs or {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        "dist",
        "build",
        ".agents",
        ".gemini",
    }

    graph = WorkspaceGraph(root_dir=wroot.as_posix())

    py_files: list[Path] = []
    for root, dirs, files in os.walk(wroot):
        dirs[:] = [d for d in dirs if d not in excluded and not d.startswith(".")]
        for file in files:
            if file.endswith(".py"):
                py_files.append(Path(root) / file)

    for py_file in py_files:
        norm_key = _normalize_path(py_file, wroot)
        graph.all_files.append(norm_key)
        graph.forward_graph[norm_key] = []
        if norm_key not in graph.reverse_graph:
            graph.reverse_graph[norm_key] = []

    for py_file in py_files:
        norm_key = _normalize_path(py_file, wroot)
        summary = extract_imports(py_file, workspace_root=wroot)
        graph.file_summaries[norm_key] = summary

        for dep in summary.internal_imports:
            graph.forward_graph[norm_key].append(dep)
            graph.reverse_graph.setdefault(dep, []).append(norm_key)

    # Sort and deduplicate adjacency lists for deterministic outputs
    for k in graph.forward_graph:
        graph.forward_graph[k] = sorted(set(graph.forward_graph[k]))
    for k in graph.reverse_graph:
        graph.reverse_graph[k] = sorted(set(graph.reverse_graph[k]))

    graph.all_files = sorted(set(graph.all_files))
    return graph


def get_affected_tests(
    changed_files: Union[str, list[str]],
    depth: int = 2,
    workspace_root: Optional[Union[str, Path]] = None,
) -> list[str]:
    """Identify all test files affected by changes to specified files up to given depth."""
    wroot = Path(workspace_root or Path.cwd()).resolve()
    if isinstance(changed_files, (str, Path)):
        files_list = [str(changed_files)]
    else:
        files_list = [str(f) for f in changed_files]

    graph = build_workspace_dependency_graph(workspace_root=wroot)
    affected_tests: set[str] = set()

    for item in files_list:
        norm_item = _normalize_path(item, wroot)

        # If a test file itself changed, include it directly
        if is_test_file(norm_item):
            affected_tests.add(norm_item)

        # Traverse reverse graph using BFS up to requested depth
        visited: set[str] = {norm_item}
        current_level: set[str] = {norm_item}

        for _ in range(depth):
            next_level: set[str] = set()
            for node in current_level:
                for dependent in graph.reverse_graph.get(node, []):
                    if dependent not in visited:
                        visited.add(dependent)
                        next_level.add(dependent)
                        if is_test_file(dependent):
                            affected_tests.add(dependent)
            current_level = next_level

    return sorted(affected_tests)


def dependency_graph(
    file_path: str,
    depth: int = 2,
    workspace_root: Optional[str] = None,
    include_stdlib: bool = False,
    include_external: bool = True,
) -> dict[str, Any]:
    """MCP Tool #5 entry point: compute dependency graph and affected tests for file."""
    wroot = Path(workspace_root or Path.cwd()).resolve()
    target_norm = _normalize_path(file_path, wroot)
    full_target_path = wroot / target_norm

    if not full_target_path.exists():
        return {
            "error": f"File '{file_path}' does not exist in workspace '{wroot.as_posix()}'.",
            "file_path": target_norm,
            "nodes": [],
            "edges": [],
            "affected_tests": [],
        }

    graph = build_workspace_dependency_graph(workspace_root=wroot)
    target_summary = graph.file_summaries.get(
        target_norm,
        extract_imports(full_target_path, workspace_root=wroot),
    )

    nodes: set[str] = {target_norm}
    edges: list[dict[str, str]] = []

    # Forward internal imports
    for dep in target_summary.internal_imports:
        nodes.add(dep)
        edges.append({"source": target_norm, "target": dep, "type": "internal"})

    # Forward external packages
    if include_external:
        for ext in target_summary.external_dependencies:
            nodes.add(ext)
            edges.append({"source": target_norm, "target": ext, "type": "external"})

    # Forward standard library
    if include_stdlib:
        for std in target_summary.standard_library:
            nodes.add(std)
            edges.append({"source": target_norm, "target": std, "type": "stdlib"})

    # Reverse direct dependents
    direct_dependents = graph.reverse_graph.get(target_norm, [])
    for dep in direct_dependents:
        nodes.add(dep)
        edges.append({"source": dep, "target": target_norm, "type": "internal"})

    affected_tests = get_affected_tests(target_norm, depth=depth, workspace_root=wroot)

    # Sort edges for deterministic output
    edges.sort(key=lambda e: (e["type"], e["source"], e["target"]))

    return {
        "file_path": target_norm,
        "nodes": sorted(nodes),
        "edges": edges,
        "internal_imports": target_summary.internal_imports,
        "external_dependencies": target_summary.external_dependencies,
        "standard_library": target_summary.standard_library,
        "dependents": direct_dependents,
        "affected_tests": affected_tests,
        "depth": depth,
    }
