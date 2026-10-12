"""Symbol Intelligence Engine for AI Coding Hub.

Provides AST-based symbol extraction (functions, async functions, classes, methods)
and cross-workspace reference scanning with syntax error resilience.
"""

import ast
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

DEFAULT_IGNORED_DIRS: Set[str] = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "env",
    "node_modules",
    ".mypy_cache",
    ".ruff_cache",
    ".agents",
    "dist",
    "build",
    ".tox",
    ".eggs",
    "htmlcov",
}


def _resolve_file_path(file_path: str, workspace_root: Optional[str] = None) -> Path:
    """Safely resolve file path and enforce workspace boundaries."""
    if workspace_root:
        root = Path(workspace_root).resolve()
        target = (root / file_path).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            raise PermissionError(
                f"Access denied: Path '{file_path}' traverses outside workspace root '{workspace_root}'."
            )
        return target
    return Path(file_path).resolve()


def _extract_signature(node: ast.AST, source_lines: List[str]) -> str:
    """Extract complete function or class signature from source lines."""
    if not hasattr(node, "lineno") or node.lineno <= 0:
        return ""
    start_idx = node.lineno - 1

    body = getattr(node, "body", [])
    if body and hasattr(body[0], "lineno") and body[0].lineno > node.lineno:
        first_body_idx = body[0].lineno - 1
        sig_chunk = source_lines[start_idx:first_body_idx]
        sig = "\n".join(sig_chunk).strip()
        if sig:
            return sig

    return source_lines[start_idx].strip() if start_idx < len(source_lines) else ""


def _collect_ast_symbols(tree: ast.AST, source_lines: List[str]) -> Dict[str, Dict[str, Any]]:
    """Traverse AST and collect all class and function symbols with qualified names."""
    symbols: Dict[str, Dict[str, Any]] = {}

    def _walk_node(node: ast.AST, parent_qname: str = "", is_class_context: bool = False):
        body = getattr(node, "body", [])
        for item in body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = item.name
                qname = f"{parent_qname}.{name}" if parent_qname else name

                if isinstance(item, ast.ClassDef):
                    kind = "class"
                elif isinstance(item, ast.AsyncFunctionDef):
                    kind = "async_method" if is_class_context else "async_function"
                else:
                    kind = "method" if is_class_context else "function"

                start_line = item.decorator_list[0].lineno if item.decorator_list else item.lineno
                end_line = getattr(item, "end_lineno", item.lineno) or item.lineno

                decorators = []
                for dec in item.decorator_list:
                    try:
                        decorators.append(f"@{ast.unparse(dec)}")
                    except Exception:
                        decorators.append(f"@{source_lines[dec.lineno - 1].strip()}")

                docstring = ast.get_docstring(item)
                signature = _extract_signature(item, source_lines)

                symbols[qname] = {
                    "name": name,
                    "qualified_name": qname,
                    "kind": kind,
                    "signature": signature,
                    "docstring": docstring,
                    "decorators": decorators,
                    "start_line": start_line,
                    "end_line": end_line,
                    "total_lines": max(1, end_line - start_line + 1),
                }

                if isinstance(item, ast.ClassDef):
                    _walk_node(item, parent_qname=qname, is_class_context=True)
                elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    _walk_node(item, parent_qname=qname, is_class_context=False)

    _walk_node(tree)
    return symbols


def read_symbol(
    file_path: str,
    symbol_name: str,
    max_body_lines: int = 200,
    workspace_root: Optional[str] = None
) -> Dict[str, Any]:
    """Extract AST-based Python symbol definition (function/class) with signature, docstring, and body.

    Args:
        file_path: Relative or absolute path to target Python file.
        symbol_name: Target symbol name or qualified name (e.g. 'Calculator.compute').
        max_body_lines: Maximum number of source body lines to return.
        workspace_root: Optional workspace root for boundary enforcement.

    Returns:
        Structured dictionary containing symbol metadata and source lines.
    """
    try:
        target_path = _resolve_file_path(file_path, workspace_root)
    except PermissionError as pe:
        return {"found": False, "error": str(pe), "file_path": file_path}
    except Exception as e:
        return {"found": False, "error": f"Invalid path '{file_path}': {e}", "file_path": file_path}

    if not target_path.exists():
        return {"found": False, "error": f"File not found: {file_path}", "file_path": file_path}
    if not target_path.is_file():
        return {"found": False, "error": f"Target is not a file: {file_path}", "file_path": file_path}

    try:
        content = target_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"found": False, "error": f"Failed reading {file_path}: {e}", "file_path": file_path}

    source_lines = content.splitlines()

    try:
        tree = ast.parse(content, filename=str(target_path))
    except (SyntaxError, IndentationError) as se:
        return {
            "found": False,
            "error": f"SyntaxError parsing {file_path}: {se.msg} (line {se.lineno}, col {se.offset})",
            "syntax_error": True,
            "line": se.lineno or 0,
            "offset": se.offset or 0,
            "file_path": file_path,
        }
    except Exception as e:
        return {
            "found": False,
            "error": f"Unexpected parse error in {file_path}: {e}",
            "file_path": file_path,
        }

    symbols = _collect_ast_symbols(tree, source_lines)

    target_symbol = None
    if symbol_name in symbols:
        target_symbol = symbols[symbol_name]
    else:
        # Search by simple name (e.g., if user passed "compute" instead of "Calculator.compute")
        matches = [sym for sym in symbols.values() if sym["name"] == symbol_name]
        if len(matches) == 1:
            target_symbol = matches[0]
        elif len(matches) > 1:
            target_symbol = matches[0]
            target_symbol["alternate_matches"] = [m["qualified_name"] for m in matches[1:]]

    if not target_symbol:
        return {
            "found": False,
            "error": f"Symbol '{symbol_name}' not found in {file_path}",
            "file_path": file_path,
            "available_symbols": sorted(list(symbols.keys())),
        }

    start = target_symbol["start_line"]
    end = target_symbol["end_line"]
    body_slice = source_lines[start - 1 : end]
    total_lines = len(body_slice)
    truncated = False

    if total_lines > max_body_lines:
        body_slice = body_slice[:max_body_lines]
        body_text = "\n".join(body_slice) + f"\n... [truncated {total_lines - max_body_lines} lines]"
        truncated = True
    else:
        body_text = "\n".join(body_slice)

    res = dict(target_symbol)
    res["found"] = True
    res["file_path"] = file_path
    res["body"] = body_text
    res["truncated"] = truncated
    return res


def list_symbols(
    file_path: str,
    workspace_root: Optional[str] = None
) -> Dict[str, Any]:
    """List all class and function symbols in a Python file.

    Args:
        file_path: Relative or absolute path to target Python file.
        workspace_root: Optional workspace root for boundary enforcement.

    Returns:
        Structured dictionary listing all symbols in file.
    """
    try:
        target_path = _resolve_file_path(file_path, workspace_root)
    except Exception as e:
        return {"error": str(e), "file_path": file_path, "total_symbols": 0, "symbols": []}

    if not target_path.exists() or not target_path.is_file():
        return {"error": f"File not found: {file_path}", "file_path": file_path, "total_symbols": 0, "symbols": []}

    try:
        content = target_path.read_text(encoding="utf-8", errors="replace")
        source_lines = content.splitlines()
        tree = ast.parse(content, filename=str(target_path))
    except (SyntaxError, IndentationError) as se:
        return {
            "error": f"SyntaxError parsing {file_path}: {se.msg}",
            "syntax_error": True,
            "file_path": file_path,
            "total_symbols": 0,
            "symbols": [],
        }
    except Exception as e:
        return {"error": f"Failed parsing {file_path}: {e}", "file_path": file_path, "total_symbols": 0, "symbols": []}

    symbols = _collect_ast_symbols(tree, source_lines)
    return {
        "file_path": file_path,
        "total_symbols": len(symbols),
        "symbols": list(symbols.values()),
    }


def find_references(
    symbol_name: str,
    workspace_root: str = ".",
    max_results: int = 100,
    include_imports: bool = True,
    include_usages: bool = True
) -> Dict[str, Any]:
    """Scan workspace for symbol definitions, imports, and usages with AST and regex fallback.

    Args:
        symbol_name: Symbol name to search across workspace.
        workspace_root: Base path for search (default '.').
        max_results: Maximum references to return (default 100).
        include_imports: Whether to match import statements (default True).
        include_usages: Whether to match identifier usages/calls (default True).

    Returns:
        Dictionary containing matching reference sites and file counts.
    """
    root = Path(workspace_root).resolve()
    if not root.exists() or not root.is_dir():
        return {
            "error": f"Workspace directory not found: {workspace_root}",
            "symbol": symbol_name,
            "total_references": 0,
            "files_scanned": 0,
            "truncated": False,
            "references": [],
            "warnings": [],
        }

    references: List[Dict[str, Any]] = []
    warnings: List[str] = []
    files_scanned = 0
    truncated = False
    regex_pattern = re.compile(rf"\b{re.escape(symbol_name)}\b")

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_IGNORED_DIRS and not d.startswith(".")]

        for fname in filenames:
            if not fname.endswith(".py"):
                continue

            file_path = Path(dirpath) / fname
            try:
                if file_path.stat().st_size > 2_000_000:
                    continue
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                warnings.append(f"Could not read {fname}: {e}")
                continue

            files_scanned += 1
            if symbol_name not in content:
                continue

            try:
                rel_path = str(file_path.relative_to(root)).replace("\\", "/")
            except ValueError:
                rel_path = str(file_path).replace("\\", "/")

            source_lines = content.splitlines()

            # Attempt AST-based scan
            try:
                tree = ast.parse(content, filename=str(file_path))

                class AstRefScanner(ast.NodeVisitor):
                    def visit_Import(self, node: ast.Import):
                        if include_imports:
                            for alias in node.names:
                                if alias.name == symbol_name or alias.asname == symbol_name:
                                    snippet = source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else ""
                                    references.append({
                                        "file": rel_path,
                                        "line": node.lineno,
                                        "col": getattr(node, "col_offset", 0) + 1,
                                        "kind": "import",
                                        "snippet": snippet,
                                    })
                        self.generic_visit(node)

                    def visit_ImportFrom(self, node: ast.ImportFrom):
                        if include_imports:
                            if node.module == symbol_name:
                                snippet = source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else ""
                                references.append({
                                    "file": rel_path,
                                    "line": node.lineno,
                                    "col": getattr(node, "col_offset", 0) + 1,
                                    "kind": "import_module",
                                    "snippet": snippet,
                                })
                            for alias in node.names:
                                if alias.name == symbol_name or alias.asname == symbol_name:
                                    snippet = source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else ""
                                    references.append({
                                        "file": rel_path,
                                        "line": node.lineno,
                                        "col": getattr(node, "col_offset", 0) + 1,
                                        "kind": "import_from",
                                        "snippet": snippet,
                                    })
                        self.generic_visit(node)

                    def visit_FunctionDef(self, node: ast.FunctionDef):
                        if include_usages and node.name == symbol_name:
                            snippet = source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else ""
                            references.append({
                                "file": rel_path,
                                "line": node.lineno,
                                "col": getattr(node, "col_offset", 0) + 1,
                                "kind": "definition",
                                "snippet": snippet,
                            })
                        self.generic_visit(node)

                    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                        if include_usages and node.name == symbol_name:
                            snippet = source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else ""
                            references.append({
                                "file": rel_path,
                                "line": node.lineno,
                                "col": getattr(node, "col_offset", 0) + 1,
                                "kind": "definition",
                                "snippet": snippet,
                            })
                        self.generic_visit(node)

                    def visit_ClassDef(self, node: ast.ClassDef):
                        if include_usages and node.name == symbol_name:
                            snippet = source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else ""
                            references.append({
                                "file": rel_path,
                                "line": node.lineno,
                                "col": getattr(node, "col_offset", 0) + 1,
                                "kind": "definition",
                                "snippet": snippet,
                            })
                        self.generic_visit(node)

                    def visit_Attribute(self, node: ast.Attribute):
                        if include_usages and node.attr == symbol_name:
                            snippet = source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else ""
                            references.append({
                                "file": rel_path,
                                "line": node.lineno,
                                "col": getattr(node, "col_offset", 0) + 1,
                                "kind": "attribute",
                                "snippet": snippet,
                            })
                        self.generic_visit(node)

                    def visit_Name(self, node: ast.Name):
                        if include_usages and node.id == symbol_name:
                            snippet = source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else ""
                            references.append({
                                "file": rel_path,
                                "line": node.lineno,
                                "col": getattr(node, "col_offset", 0) + 1,
                                "kind": "usage",
                                "snippet": snippet,
                            })
                        self.generic_visit(node)

                AstRefScanner().visit(tree)

            except (SyntaxError, IndentationError) as se:
                warnings.append(f"SyntaxError in {rel_path}: {se.msg}; fell back to regex scan.")
                for line_num, line in enumerate(source_lines, 1):
                    for match in regex_pattern.finditer(line):
                        references.append({
                            "file": rel_path,
                            "line": line_num,
                            "col": match.start() + 1,
                            "kind": "regex_fallback",
                            "snippet": line.strip(),
                        })

            if len(references) >= max_results:
                truncated = True
                break
        if truncated:
            break

    # Deduplicate entries by (file, line, col, kind)
    seen = set()
    deduped = []
    for r in references:
        key = (r["file"], r["line"], r["col"], r["kind"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    if len(deduped) > max_results:
        deduped = deduped[:max_results]
        truncated = True

    return {
        "symbol": symbol_name,
        "total_references": len(deduped),
        "files_scanned": files_scanned,
        "truncated": truncated,
        "references": deduped,
        "warnings": warnings,
    }
