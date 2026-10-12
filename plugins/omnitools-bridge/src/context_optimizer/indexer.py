"""OmniTools Universal AI Bridge - High-Performance Incremental Indexer & AST Symbol Cache

Provides two-tier incremental indexing (mtime_ns + SHA256) and AST-based
symbol caching with atomic persistence and cross-platform path normalization.
"""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple


# ==============================================================================
# 1. DATA MODELS & ENUMS
# ==============================================================================

class SymbolKind(str, Enum):
    """Classification of code symbols extracted by the AST parser."""
    FUNCTION = "function"
    ASYNC_FUNCTION = "async_function"
    CLASS = "class"
    METHOD = "method"
    ASYNC_METHOD = "async_method"
    VARIABLE = "variable"
    IMPORT = "import"


@dataclass
class SymbolRecord:
    """Represents an extracted code symbol and its structural metadata."""
    name: str
    qualified_name: str
    kind: SymbolKind
    line_start: int
    line_end: int
    col_offset: int = 0
    end_col_offset: int = 0
    signature: Optional[str] = None
    docstring: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    parameters: List[str] = field(default_factory=list)
    return_type: Optional[str] = None
    parent_symbol: Optional[str] = None
    is_exported: bool = True

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["kind"] = self.kind.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SymbolRecord:
        d = dict(data)
        d["kind"] = SymbolKind(d["kind"])
        return cls(**d)


@dataclass
class ImportRecord:
    """Represents an import statement extracted from Python source code."""
    module: str
    names: List[str] = field(default_factory=list)
    alias: Optional[str] = None
    is_from: bool = False
    line_no: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ImportRecord:
        return cls(**data)


@dataclass
class FileIndexEntry:
    """Represents an indexed source file with metadata, symbols, and content hash."""
    rel_path: str
    mtime_ns: int
    size_bytes: int
    sha256: str
    symbols: List[SymbolRecord] = field(default_factory=list)
    imports: List[ImportRecord] = field(default_factory=list)
    line_count: int = 0
    has_syntax_error: bool = False
    error_message: Optional[str] = None
    indexed_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rel_path": self.rel_path,
            "mtime_ns": self.mtime_ns,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "symbols": [s.to_dict() for s in self.symbols],
            "imports": [i.to_dict() for i in self.imports],
            "line_count": self.line_count,
            "has_syntax_error": self.has_syntax_error,
            "error_message": self.error_message,
            "indexed_at": self.indexed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FileIndexEntry:
        return cls(
            rel_path=data["rel_path"],
            mtime_ns=data["mtime_ns"],
            size_bytes=data["size_bytes"],
            sha256=data["sha256"],
            symbols=[SymbolRecord.from_dict(s) for s in data.get("symbols", [])],
            imports=[ImportRecord.from_dict(i) for i in data.get("imports", [])],
            line_count=data.get("line_count", 0),
            has_syntax_error=data.get("has_syntax_error", False),
            error_message=data.get("error_message"),
            indexed_at=data.get("indexed_at", 0.0),
        )


@dataclass
class IndexStats:
    """Summary statistics for an incremental workspace indexing run."""
    total_files: int = 0
    scanned_files: int = 0
    indexed_files: int = 0
    cached_files: int = 0
    deleted_files: int = 0
    total_symbols: int = 0
    duration_ms: float = 0.0
    cache_hit_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ==============================================================================
# 2. HASH & AST HELPERS
# ==============================================================================

def compute_sha256(content: str | bytes) -> str:
    """Compute SHA256 hexadecimal digest of text or bytes."""
    if isinstance(content, str):
        content_bytes = content.encode("utf-8")
    else:
        content_bytes = content
    return hashlib.sha256(content_bytes).hexdigest()


def _format_argument(arg: ast.arg, default: Optional[ast.AST] = None) -> str:
    """Format an individual AST function argument with its type annotation and default value."""
    result = arg.arg
    if arg.annotation:
        try:
            ann_str = ast.unparse(arg.annotation)
            result += f": {ann_str}"
        except Exception:
            pass
    if default is not None:
        try:
            def_str = ast.unparse(default)
            result += f" = {def_str}"
        except Exception:
            result += " = ..."
    return result


def _extract_function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Reconstruct function/method parameter list and return type annotation."""
    args = node.args
    arg_strings: List[str] = []

    # Positional-only arguments
    num_posonly = len(getattr(args, "posonlyargs", []))
    posonly_defaults_start = num_posonly + len(args.args) - len(args.defaults)

    for i, a in enumerate(getattr(args, "posonlyargs", [])):
        default = None
        if i >= posonly_defaults_start:
            default_idx = i - posonly_defaults_start
            if 0 <= default_idx < len(args.defaults):
                default = args.defaults[default_idx]
        arg_strings.append(_format_argument(a, default))

    if num_posonly > 0:
        arg_strings.append("/")

    # Standard positional/keyword arguments
    pos_defaults_start = len(args.args) - len(args.defaults)
    for i, a in enumerate(args.args):
        default = None
        if i >= pos_defaults_start:
            default_idx = i - pos_defaults_start
            if 0 <= default_idx < len(args.defaults):
                default = args.defaults[default_idx]
        arg_strings.append(_format_argument(a, default))

    # *vararg
    if args.vararg:
        prefix = f"*{args.vararg.arg}"
        if args.vararg.annotation:
            try:
                prefix += f": {ast.unparse(args.vararg.annotation)}"
            except Exception:
                pass
        arg_strings.append(prefix)
    elif args.kwonlyargs:
        arg_strings.append("*")

    # Keyword-only arguments
    for i, a in enumerate(args.kwonlyargs):
        default = args.kw_defaults[i] if i < len(args.kw_defaults) else None
        arg_strings.append(_format_argument(a, default))

    # **kwarg
    if args.kwarg:
        prefix = f"**{args.kwarg.arg}"
        if args.kwarg.annotation:
            try:
                prefix += f": {ast.unparse(args.kwarg.annotation)}"
            except Exception:
                pass
        arg_strings.append(prefix)

    sig = f"({', '.join(arg_strings)})"
    if node.returns:
        try:
            ret_str = ast.unparse(node.returns)
            sig += f" -> {ret_str}"
        except Exception:
            pass

    return sig


def _extract_decorators(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> List[str]:
    """Extract decorator strings for a function, method, or class node."""
    decorators: List[str] = []
    for d in node.decorator_list:
        try:
            decorators.append(ast.unparse(d))
        except Exception:
            decorators.append(type(d).__name__)
    return decorators


# ==============================================================================
# 3. AST SYMBOL VISITOR
# ==============================================================================

class _ASTSymbolVisitor(ast.NodeVisitor):
    """Walks Python AST to discover classes, functions, methods, and imports."""

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.symbols: List[SymbolRecord] = []
        self.imports: List[ImportRecord] = []
        self._class_stack: List[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        parent_class = self._class_stack[-1] if self._class_stack else None
        qname = f"{parent_class}.{node.name}" if parent_class else node.name

        doc = ast.get_docstring(node)
        decorators = _extract_decorators(node)

        # Base classes in signature
        base_names: List[str] = []
        for b in node.bases:
            try:
                base_names.append(ast.unparse(b))
            except Exception:
                base_names.append(type(b).__name__)
        sig = f"class {node.name}({', '.join(base_names)})" if base_names else f"class {node.name}"

        end_line = getattr(node, "end_lineno", node.lineno)

        self.symbols.append(
            SymbolRecord(
                name=node.name,
                qualified_name=qname,
                kind=SymbolKind.CLASS,
                line_start=node.lineno,
                line_end=end_line,
                col_offset=node.col_offset,
                end_col_offset=getattr(node, "end_col_offset", 0),
                signature=sig,
                docstring=doc,
                decorators=decorators,
                parent_symbol=parent_class,
                is_exported=not node.name.startswith("_") or node.name.startswith("__"),
            )
        )

        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._handle_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._handle_function(node, is_async=True)

    def _handle_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool
    ) -> None:
        parent_class = self._class_stack[-1] if self._class_stack else None
        qname = f"{parent_class}.{node.name}" if parent_class else node.name

        if parent_class:
            kind = SymbolKind.ASYNC_METHOD if is_async else SymbolKind.METHOD
        else:
            kind = SymbolKind.ASYNC_FUNCTION if is_async else SymbolKind.FUNCTION

        doc = ast.get_docstring(node)
        decorators = _extract_decorators(node)
        sig = _extract_function_signature(node)

        return_type = None
        if node.returns:
            try:
                return_type = ast.unparse(node.returns)
            except Exception:
                pass

        params: List[str] = []
        for a in getattr(node.args, "posonlyargs", []) + node.args.args + node.args.kwonlyargs:
            params.append(a.arg)
        if node.args.vararg:
            params.append(f"*{node.args.vararg.arg}")
        if node.args.kwarg:
            params.append(f"**{node.args.kwarg.arg}")

        end_line = getattr(node, "end_lineno", node.lineno)

        self.symbols.append(
            SymbolRecord(
                name=node.name,
                qualified_name=qname,
                kind=kind,
                line_start=node.lineno,
                line_end=end_line,
                col_offset=node.col_offset,
                end_col_offset=getattr(node, "end_col_offset", 0),
                signature=sig,
                docstring=doc,
                decorators=decorators,
                parameters=params,
                return_type=return_type,
                parent_symbol=parent_class,
                is_exported=not node.name.startswith("_") or node.name.startswith("__"),
            )
        )

        # Do not recurse into inner functions if top-level, or do recurse if we want nested symbols
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        # Capture module-level uppercase constants
        if not self._class_stack:
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    val_str = None
                    try:
                        val_str = ast.unparse(node.value)
                    except Exception:
                        pass
                    self.symbols.append(
                        SymbolRecord(
                            name=target.id,
                            qualified_name=target.id,
                            kind=SymbolKind.VARIABLE,
                            line_start=node.lineno,
                            line_end=getattr(node, "end_lineno", node.lineno),
                            col_offset=node.col_offset,
                            end_col_offset=getattr(node, "end_col_offset", 0),
                            signature=f"{target.id} = {val_str}" if val_str else target.id,
                            is_exported=not target.id.startswith("_"),
                        )
                    )
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        # Capture module-level typed constants/variables
        if not self._class_stack and isinstance(node.target, ast.Name) and node.target.id.isupper():
            ann_str = ""
            try:
                ann_str = f": {ast.unparse(node.annotation)}"
            except Exception:
                pass
            val_str = ""
            if node.value:
                try:
                    val_str = f" = {ast.unparse(node.value)}"
                except Exception:
                    pass
            self.symbols.append(
                SymbolRecord(
                    name=node.target.id,
                    qualified_name=node.target.id,
                    kind=SymbolKind.VARIABLE,
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", node.lineno),
                    col_offset=node.col_offset,
                    end_col_offset=getattr(node, "end_col_offset", 0),
                    signature=f"{node.target.id}{ann_str}{val_str}",
                    is_exported=not node.target.id.startswith("_"),
                )
            )
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(
                ImportRecord(
                    module=alias.name,
                    names=[alias.asname or alias.name],
                    alias=alias.asname,
                    is_from=False,
                    line_no=node.lineno,
                )
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module_name = node.module or ""
        names = [alias.name for alias in node.names]
        self.imports.append(
            ImportRecord(
                module=module_name,
                names=names,
                alias=None,
                is_from=True,
                line_no=node.lineno,
            )
        )
        self.generic_visit(node)


# ==============================================================================
# 4. CODE INDEXER ENGINE
# ==============================================================================

DEFAULT_EXCLUDES = [
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "node_modules",
    ".agents",
    "dist",
    "build",
    ".egg-info",
    ".mypy_cache",
    ".tox",
    ".cache",
]


class CodeIndexer:
    """Incremental code indexer and symbol cache engine.

    Uses two-tier invalidation (mtime_ns + SHA256) and atomic persistence
    for maximum performance and token efficiency.
    """

    def __init__(
        self,
        workspace_root: str | Path = ".",
        cache_path: Optional[str | Path] = None,
        exclude_patterns: Optional[List[str]] = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.exclude_patterns = exclude_patterns or list(DEFAULT_EXCLUDES)

        if cache_path is not None:
            self.cache_path = Path(cache_path).resolve()
        else:
            self.cache_path = self.workspace_root / ".cache" / "context_optimizer" / "index.json"

        self._cache: Dict[str, FileIndexEntry] = {}
        self._symbol_table: Dict[str, List[SymbolRecord]] = {}
        self._lock = threading.RLock()

        # Load existing cache if present
        self.load_cache()

    # --------------------------------------------------------------------------
    # Path & Filtering Utilities
    # --------------------------------------------------------------------------

    def _normalize_rel_path(self, path: str | Path) -> str:
        """Convert a path to a normalized relative POSIX string for cross-platform portability."""
        p = Path(path)
        if p.is_absolute():
            try:
                rel = p.relative_to(self.workspace_root)
            except ValueError:
                rel = p
        else:
            rel = p
        return rel.as_posix()

    def _should_exclude(self, rel_path: str) -> bool:
        """Check if relative path matches any exclusion rule."""
        parts = rel_path.split("/")
        for pattern in self.exclude_patterns:
            if pattern in parts:
                return True
            for part in parts:
                if part.startswith(pattern) or part.endswith(pattern):
                    return True
        return False

    # --------------------------------------------------------------------------
    # Invalidation & Indexing
    # --------------------------------------------------------------------------

    def is_file_modified(self, file_path: str | Path) -> bool:
        """Check whether a file needs re-indexing via Tier 1 (mtime+size) and Tier 2 (SHA256)."""
        rel_path = self._normalize_rel_path(file_path)
        abs_path = self.workspace_root / rel_path

        if not abs_path.is_file():
            return True

        with self._lock:
            cached = self._cache.get(rel_path)
            if cached is None:
                return True

            try:
                stat = abs_path.stat()
            except OSError:
                return True

            # Tier 1 fast check
            if stat.st_mtime_ns == cached.mtime_ns and stat.st_size == cached.size_bytes:
                return False

            # Tier 2 content hash check
            try:
                content = abs_path.read_bytes()
                new_hash = hashlib.sha256(content).hexdigest()
                return new_hash != cached.sha256
            except OSError:
                return True

    def invalidate(self, file_path: str | Path) -> bool:
        """Invalidate and remove a file from cache and symbol table."""
        rel_path = self._normalize_rel_path(file_path)
        with self._lock:
            if rel_path in self._cache:
                del self._cache[rel_path]
                self._rebuild_symbol_table()
                return True
            return False

    def index_file(self, file_path: str | Path, force: bool = False) -> Optional[FileIndexEntry]:
        """Index a single file incrementally.

        Returns:
            FileIndexEntry: Cached or newly indexed file entry, or None if file cannot be read.
        """
        rel_path = self._normalize_rel_path(file_path)
        abs_path = self.workspace_root / rel_path

        if not abs_path.is_file():
            self.invalidate(rel_path)
            return None

        try:
            stat = abs_path.stat()
        except OSError:
            return None

        with self._lock:
            cached = self._cache.get(rel_path)

            # Tier 1: Check mtime_ns and size_bytes
            if not force and cached is not None:
                if stat.st_mtime_ns == cached.mtime_ns and stat.st_size == cached.size_bytes:
                    return cached

            # Read content for Tier 2 and AST parsing
            try:
                content_bytes = abs_path.read_bytes()
            except OSError:
                return None

            sha256 = hashlib.sha256(content_bytes).hexdigest()

            # Tier 2: Check content hash
            if not force and cached is not None and cached.sha256 == sha256:
                # Content identical; update mtime_ns and size_bytes without re-parsing AST
                cached.mtime_ns = stat.st_mtime_ns
                cached.size_bytes = stat.st_size
                return cached

            # Tier 3: Parse AST and extract symbols
            try:
                content_text = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    content_text = content_bytes.decode("latin-1")
                except Exception as err:
                    entry = FileIndexEntry(
                        rel_path=rel_path,
                        mtime_ns=stat.st_mtime_ns,
                        size_bytes=stat.st_size,
                        sha256=sha256,
                        has_syntax_error=True,
                        error_message=f"Decode error: {err}",
                        indexed_at=time.time(),
                    )
                    self._cache[rel_path] = entry
                    self._rebuild_symbol_table()
                    return entry

            line_count = len(content_text.splitlines())

            try:
                tree = ast.parse(content_text, filename=rel_path)
                visitor = _ASTSymbolVisitor(rel_path)
                visitor.visit(tree)
                symbols = visitor.symbols
                imports = visitor.imports
                has_syntax_error = False
                error_message = None
            except SyntaxError as err:
                symbols = []
                imports = []
                has_syntax_error = True
                error_message = f"SyntaxError at line {err.lineno}: {err.msg}"
            except Exception as err:
                symbols = []
                imports = []
                has_syntax_error = True
                error_message = f"AST parse error: {err}"

            entry = FileIndexEntry(
                rel_path=rel_path,
                mtime_ns=stat.st_mtime_ns,
                size_bytes=stat.st_size,
                sha256=sha256,
                symbols=symbols,
                imports=imports,
                line_count=line_count,
                has_syntax_error=has_syntax_error,
                error_message=error_message,
                indexed_at=time.time(),
            )

            self._cache[rel_path] = entry
            self._rebuild_symbol_table()
            return entry

    def scan_workspace(self, force: bool = False) -> IndexStats:
        """Scan workspace recursively, incrementally indexing Python files.

        Returns:
            IndexStats: Performance and indexing results.
        """
        start_time = time.perf_counter()
        scanned_count = 0
        indexed_count = 0
        cached_count = 0
        discovered_rel_paths: Set[str] = set()

        # Walk directory
        for root, dirs, files in os.walk(self.workspace_root):
            # Prune excluded directories in-place
            dirs[:] = [
                d for d in dirs
                if not self._should_exclude(
                    self._normalize_rel_path(Path(root) / d)
                )
            ]

            for file in files:
                if not file.endswith(".py"):
                    continue

                full_path = Path(root) / file
                rel_posix = self._normalize_rel_path(full_path)

                if self._should_exclude(rel_posix):
                    continue

                discovered_rel_paths.add(rel_posix)
                scanned_count += 1

                # Check if it will be a cache hit before indexing
                was_cached = (
                    not force
                    and rel_posix in self._cache
                    and not self.is_file_modified(full_path)
                )

                entry = self.index_file(full_path, force=force)
                if entry is not None:
                    if was_cached:
                        cached_count += 1
                    else:
                        indexed_count += 1

        # Purge deleted files
        with self._lock:
            existing_cached = set(self._cache.keys())
            deleted_paths = existing_cached - discovered_rel_paths
            for d in deleted_paths:
                del self._cache[d]

            if deleted_paths:
                self._rebuild_symbol_table()

            total_symbols = sum(len(e.symbols) for e in self._cache.values())

        # Save cache atomically
        self.save_cache()

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        hit_rate = (cached_count / scanned_count * 100.0) if scanned_count > 0 else 100.0

        return IndexStats(
            total_files=len(self._cache),
            scanned_files=scanned_count,
            indexed_files=indexed_count,
            cached_files=cached_count,
            deleted_files=len(deleted_paths),
            total_symbols=total_symbols,
            duration_ms=round(duration_ms, 2),
            cache_hit_rate=round(hit_rate, 2),
        )

    # --------------------------------------------------------------------------
    # Symbol Table & Lookup
    # --------------------------------------------------------------------------

    def _rebuild_symbol_table(self) -> None:
        """Rebuild in-memory inverted symbol table from current cache entries."""
        new_table: Dict[str, List[SymbolRecord]] = {}
        for entry in self._cache.values():
            for sym in entry.symbols:
                new_table.setdefault(sym.name, []).append(sym)
                if sym.qualified_name != sym.name:
                    new_table.setdefault(sym.qualified_name, []).append(sym)
        self._symbol_table = new_table

    def find_symbol(self, name: str, exact: bool = True) -> List[SymbolRecord]:
        """Lookup symbols by name or prefix across all indexed files."""
        with self._lock:
            if exact:
                return list(self._symbol_table.get(name, []))

            # Fuzzy / prefix search
            name_lower = name.lower()
            results: List[SymbolRecord] = []
            for sym_name, records in self._symbol_table.items():
                if name_lower in sym_name.lower():
                    results.extend(records)
            return results

    def find_symbols_by_kind(self, kind: SymbolKind | str) -> List[SymbolRecord]:
        """Find all symbols matching a specific SymbolKind."""
        target_kind = kind if isinstance(kind, SymbolKind) else SymbolKind(kind)
        results: List[SymbolRecord] = []
        with self._lock:
            for entry in self._cache.values():
                for sym in entry.symbols:
                    if sym.kind == target_kind:
                        results.append(sym)
        return results

    def get_file_symbols(self, file_path: str | Path) -> List[SymbolRecord]:
        """Retrieve all symbols for a specific file."""
        rel_path = self._normalize_rel_path(file_path)
        with self._lock:
            entry = self._cache.get(rel_path)
            return list(entry.symbols) if entry else []

    def get_file_imports(self, file_path: str | Path) -> List[ImportRecord]:
        """Retrieve all imports for a specific file."""
        rel_path = self._normalize_rel_path(file_path)
        with self._lock:
            entry = self._cache.get(rel_path)
            return list(entry.imports) if entry else []

    def get_entry(self, file_path: str | Path) -> Optional[FileIndexEntry]:
        """Get the cached FileIndexEntry for a given file."""
        rel_path = self._normalize_rel_path(file_path)
        with self._lock:
            return self._cache.get(rel_path)

    def get_all_symbols(self) -> Dict[str, List[SymbolRecord]]:
        """Return a copy of the inverted symbol table."""
        with self._lock:
            return {k: list(v) for k, v in self._symbol_table.items()}

    def get_indexed_files(self) -> List[str]:
        """Return list of all indexed relative file paths."""
        with self._lock:
            return list(self._cache.keys())

    def clear_cache(self) -> None:
        """Clear in-memory and disk cache."""
        with self._lock:
            self._cache.clear()
            self._symbol_table.clear()
            if self.cache_path.exists():
                try:
                    self.cache_path.unlink()
                except OSError:
                    pass

    # --------------------------------------------------------------------------
    # Persistence
    # --------------------------------------------------------------------------

    def save_cache(self, custom_path: Optional[str | Path] = None) -> None:
        """Save index cache to disk atomically using temporary file replace."""
        target_path = Path(custom_path).resolve() if custom_path else self.cache_path
        target_path.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            payload = {
                "version": "2.0.0",
                "workspace_root": self.workspace_root.as_posix(),
                "saved_at": time.time(),
                "entries": {k: v.to_dict() for k, v in self._cache.items()},
            }

        temp_path = target_path.with_suffix(f".tmp.{os.getpid()}")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            os.replace(temp_path, target_path)
        except Exception:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            raise

    def load_cache(self, custom_path: Optional[str | Path] = None) -> bool:
        """Load index cache from disk.

        Returns:
            bool: True if loaded successfully, False otherwise.
        """
        target_path = Path(custom_path).resolve() if custom_path else self.cache_path
        if not target_path.is_file():
            return False

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            entries_raw = data.get("entries", {})
            new_cache: Dict[str, FileIndexEntry] = {}
            for rel_path, entry_data in entries_raw.items():
                new_cache[rel_path] = FileIndexEntry.from_dict(entry_data)

            with self._lock:
                self._cache = new_cache
                self._rebuild_symbol_table()
            return True
        except Exception:
            # Corrupted cache: start fresh safely
            with self._lock:
                self._cache.clear()
                self._symbol_table.clear()
            return False


# ==============================================================================
# 5. MODULE-LEVEL SINGLETON & CONVENIENCE API
# ==============================================================================

_DEFAULT_INDEXER: Optional[CodeIndexer] = None
_INDEXER_LOCK = threading.Lock()


def get_indexer(workspace_root: Optional[str | Path] = None) -> CodeIndexer:
    """Get or initialize the global CodeIndexer instance."""
    global _DEFAULT_INDEXER
    with _INDEXER_LOCK:
        if _DEFAULT_INDEXER is None or (
            workspace_root is not None
            and Path(workspace_root).resolve() != _DEFAULT_INDEXER.workspace_root
        ):
            root = workspace_root or Path.cwd()
            _DEFAULT_INDEXER = CodeIndexer(workspace_root=root)
        return _DEFAULT_INDEXER


def index_workspace(workspace_root: Optional[str | Path] = None, force: bool = False) -> IndexStats:
    """Convenience function to scan and index workspace."""
    indexer = get_indexer(workspace_root)
    return indexer.scan_workspace(force=force)


def find_symbol_in_workspace(
    name: str, workspace_root: Optional[str | Path] = None, exact: bool = True
) -> List[SymbolRecord]:
    """Convenience function to lookup a symbol across workspace."""
    indexer = get_indexer(workspace_root)
    return indexer.find_symbol(name, exact=exact)
