"""OmniTools Universal AI Bridge - Context Compression Engine

High-performance, AST-driven context compression engine for inter-agent handoff.
Extracts concise symbol outlines, key signatures, type annotations, and public
interfaces while stripping implementation bodies to eliminate token bloat.

Features:
- Precise Python AST visitor preserving classes, methods, signatures, and types.
- Elimination of implementation bodies replaced with standard ellipsis (`...`).
- First-line docstring condensation and optional stripping.
- Public API filtering (omits internal symbols unless requested).
- Multi-file repository context aggregation with per-file savings metrics.
- 4-Tier adaptive budget pruning under strict max_tokens constraints.
- Resilient fallback regex parser for non-Python or malformed sources.
- Multi-format output: PEP 484 stub (".pyi" style), Markdown outline, or JSON.
"""

from __future__ import annotations

import ast
import copy
from dataclasses import asdict, dataclass, field
from enum import Enum
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Common Python dunder methods that define critical public contracts
ALLOWED_DUNDERS: Set[str] = {
    "__init__",
    "__call__",
    "__enter__",
    "__exit__",
    "__aenter__",
    "__aexit__",
    "__getitem__",
    "__setitem__",
    "__delitem__",
    "__iter__",
    "__next__",
    "__anext__",
    "__len__",
    "__repr__",
    "__str__",
    "__bool__",
    "__eq__",
    "__contains__",
}


class SymbolType(str, Enum):
    """Enumeration of recognized code symbol categories."""

    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    ASYNC_FUNCTION = "async_function"
    METHOD = "method"
    ASYNC_METHOD = "async_method"
    VARIABLE = "variable"
    TYPE_ALIAS = "type_alias"


@dataclass
class SymbolOutline:
    """Represents a single extracted code symbol and its signature hierarchy."""

    name: str
    symbol_type: SymbolType
    signature: Optional[str] = None
    docstring: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    children: List["SymbolOutline"] = field(default_factory=list)
    line_number: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert the symbol outline to a JSON-serializable dictionary."""
        return {
            "name": self.name,
            "symbol_type": self.symbol_type.value,
            "signature": self.signature,
            "docstring": self.docstring,
            "decorators": self.decorators,
            "children": [child.to_dict() for child in self.children],
            "line_number": self.line_number,
        }


@dataclass
class CompressionStats:
    """Compression performance metrics comparing raw source against compressed output."""

    original_chars: int = 0
    compressed_chars: int = 0
    original_tokens_est: int = 0
    compressed_tokens_est: int = 0
    compression_ratio: float = 0.0
    tokens_saved_pct: float = 0.0
    symbol_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert compression stats to a dictionary."""
        return asdict(self)


@dataclass
class ContextSummary:
    """Complete compressed context summary prepared for inter-agent handoffs."""

    outline_text: str
    symbols: List[SymbolOutline] = field(default_factory=list)
    stats: CompressionStats = field(default_factory=CompressionStats)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert entire context summary to a serializable dictionary."""
        return {
            "outline_text": self.outline_text,
            "symbols": [s.to_dict() for s in self.symbols],
            "stats": self.stats.to_dict(),
            "metadata": self.metadata,
        }

    def __str__(self) -> str:
        return self.outline_text


def estimate_tokens(text: str) -> int:
    """Estimate token count using code-aware heuristic (~3.8 chars per token)."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def _condense_docstring(doc: Optional[str], max_lines: int = 1) -> Optional[str]:
    """Condense multi-line docstring into concise summary (up to max_lines)."""
    if not doc:
        return None
    cleaned = doc.strip()
    if not cleaned:
        return None
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if not lines:
        return None
    selected = lines[:max_lines]
    condensed = " ".join(selected)
    # Truncate overly verbose single lines to avoid token leaks
    if len(condensed) > 240:
        condensed = condensed[:237].rstrip() + "..."
    return condensed


def _is_private_symbol(name: str) -> bool:
    """Check if a symbol name is private/internal, excluding allowed dunders."""
    if name.startswith("_"):
        if name in ALLOWED_DUNDERS:
            return False
        return True
    return False


class PythonASTCompressor:
    """AST visitor and transformer that extracts interface stubs from Python source."""

    def __init__(
        self,
        include_private: bool = False,
        include_docstrings: bool = True,
        max_docstring_lines: int = 1,
        include_imports: bool = False,
    ) -> None:
        self.include_private = include_private
        self.include_docstrings = include_docstrings
        self.max_docstring_lines = max_docstring_lines
        self.include_imports = include_imports

    def compress(self, source_code: str, file_name: Optional[str] = None) -> Tuple[str, List[SymbolOutline]]:
        """Parse source code via AST and produce compressed outline text and symbol list."""
        tree = ast.parse(source_code, filename=file_name or "<source>")

        symbols: List[SymbolOutline] = []
        stub_nodes: List[ast.AST] = []

        # 1. Module Docstring
        mod_doc = ast.get_docstring(tree)
        condensed_mod_doc = _condense_docstring(mod_doc, self.max_docstring_lines)
        if self.include_docstrings and condensed_mod_doc:
            stub_nodes.append(ast.Expr(value=ast.Constant(value=condensed_mod_doc)))

        # 2. Iterate top-level statements
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if self.include_imports:
                    stub_nodes.append(copy.deepcopy(node))

            elif isinstance(node, ast.ClassDef):
                if not self.include_private and _is_private_symbol(node.name):
                    continue
                sym, stub_cls = self._process_class(node)
                symbols.append(sym)
                stub_nodes.append(stub_cls)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not self.include_private and _is_private_symbol(node.name):
                    continue
                sym, stub_fn = self._process_function(node, is_method=False)
                symbols.append(sym)
                stub_nodes.append(stub_fn)

            elif isinstance(node, ast.AnnAssign):
                # Class or module type annotation: e.g., `TIMEOUT: int = 30`
                var_name = self._get_target_name(node.target)
                if var_name:
                    if not self.include_private and _is_private_symbol(var_name):
                        continue
                    sym = SymbolOutline(
                        name=var_name,
                        symbol_type=SymbolType.VARIABLE,
                        signature=ast.unparse(node),
                        line_number=getattr(node, "lineno", None),
                    )
                    symbols.append(sym)
                    # Create stub assignment
                    stub_assign = copy.deepcopy(node)
                    if stub_assign.value is not None:
                        stub_assign.value = ast.Constant(value=Ellipsis)
                    stub_nodes.append(stub_assign)

            elif isinstance(node, ast.Assign):
                # Public constants or `__all__`
                for target in node.targets:
                    var_name = self._get_target_name(target)
                    if var_name:
                        if not self.include_private and _is_private_symbol(var_name):
                            continue
                        if var_name == "__all__" or (var_name.isupper() and len(var_name) > 1):
                            sym = SymbolOutline(
                                name=var_name,
                                symbol_type=SymbolType.VARIABLE,
                                signature=ast.unparse(node),
                                line_number=getattr(node, "lineno", None),
                            )
                            symbols.append(sym)
                            stub_assign = copy.deepcopy(node)
                            # Keep __all__ literal intact for API visibility; ellipsis for large constants
                            if var_name != "__all__":
                                stub_assign.value = ast.Constant(value=Ellipsis)
                            stub_nodes.append(stub_assign)

        # Assemble stub AST module and unparse
        stub_module = ast.Module(body=stub_nodes, type_ignores=[])
        ast.fix_missing_locations(stub_module)
        outline_text = ast.unparse(stub_module)

        return outline_text, symbols

    def _process_class(self, node: ast.ClassDef) -> Tuple[SymbolOutline, ast.ClassDef]:
        """Extract symbol details and build stubbed ClassDef."""
        cls_doc = ast.get_docstring(node)
        condensed_doc = _condense_docstring(cls_doc, self.max_docstring_lines)

        decorators = [ast.unparse(d) for d in node.decorator_list]
        bases = [ast.unparse(b) for b in node.bases]
        sig_header = f"class {node.name}"
        if bases:
            sig_header += f"({', '.join(bases)})"

        child_symbols: List[SymbolOutline] = []
        class_stub_body: List[ast.AST] = []

        if self.include_docstrings and condensed_doc:
            class_stub_body.append(ast.Expr(value=ast.Constant(value=condensed_doc)))

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not self.include_private and _is_private_symbol(item.name):
                    continue
                method_sym, stub_method = self._process_function(item, is_method=True)
                child_symbols.append(method_sym)
                class_stub_body.append(stub_method)

            elif isinstance(item, ast.AnnAssign):
                attr_name = self._get_target_name(item.target)
                if attr_name:
                    if not self.include_private and _is_private_symbol(attr_name):
                        continue
                    attr_sym = SymbolOutline(
                        name=attr_name,
                        symbol_type=SymbolType.VARIABLE,
                        signature=ast.unparse(item),
                        line_number=getattr(item, "lineno", None),
                    )
                    child_symbols.append(attr_sym)
                    stub_attr = copy.deepcopy(item)
                    if stub_attr.value is not None:
                        stub_attr.value = ast.Constant(value=Ellipsis)
                    class_stub_body.append(stub_attr)

            elif isinstance(item, ast.ClassDef):
                if not self.include_private and _is_private_symbol(item.name):
                    continue
                nested_sym, stub_nested = self._process_class(item)
                child_symbols.append(nested_sym)
                class_stub_body.append(stub_nested)

        if not class_stub_body:
            class_stub_body.append(ast.Expr(value=ast.Constant(value=Ellipsis)))

        stub_cls = ast.ClassDef(
            name=node.name,
            bases=copy.deepcopy(node.bases),
            keywords=copy.deepcopy(node.keywords),
            body=class_stub_body,
            decorator_list=copy.deepcopy(node.decorator_list),
        )
        ast.copy_location(stub_cls, node)

        cls_outline = SymbolOutline(
            name=node.name,
            symbol_type=SymbolType.CLASS,
            signature=sig_header,
            docstring=condensed_doc,
            decorators=decorators,
            children=child_symbols,
            line_number=getattr(node, "lineno", None),
        )
        return cls_outline, stub_cls

    def _process_function(
        self,
        node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
        is_method: bool = False,
    ) -> Tuple[SymbolOutline, Union[ast.FunctionDef, ast.AsyncFunctionDef]]:
        """Extract symbol details and build stubbed function or method node."""
        fn_doc = ast.get_docstring(node)
        condensed_doc = _condense_docstring(fn_doc, self.max_docstring_lines)
        decorators = [ast.unparse(d) for d in node.decorator_list]

        if is_method:
            stype = SymbolType.ASYNC_METHOD if isinstance(node, ast.AsyncFunctionDef) else SymbolType.METHOD
        else:
            stype = SymbolType.ASYNC_FUNCTION if isinstance(node, ast.AsyncFunctionDef) else SymbolType.FUNCTION

        # Build clean signature string
        clean_node = copy.deepcopy(node)
        clean_node.body = [ast.Pass()]
        clean_node.decorator_list = []
        ast.fix_missing_locations(clean_node)
        unparsed = ast.unparse(clean_node).strip()
        sig_line = unparsed.splitlines()[0] if unparsed else f"def {node.name}(...):"

        stub_body: List[ast.AST] = []
        if self.include_docstrings and condensed_doc:
            stub_body.append(ast.Expr(value=ast.Constant(value=condensed_doc)))
        stub_body.append(ast.Expr(value=ast.Constant(value=Ellipsis)))

        if isinstance(node, ast.AsyncFunctionDef):
            stub_fn = ast.AsyncFunctionDef(
                name=node.name,
                args=copy.deepcopy(node.args),
                body=stub_body,
                decorator_list=copy.deepcopy(node.decorator_list),
                returns=copy.deepcopy(node.returns),
                type_comment=getattr(node, "type_comment", None),
            )
        else:
            stub_fn = ast.FunctionDef(
                name=node.name,
                args=copy.deepcopy(node.args),
                body=stub_body,
                decorator_list=copy.deepcopy(node.decorator_list),
                returns=copy.deepcopy(node.returns),
                type_comment=getattr(node, "type_comment", None),
            )
        ast.copy_location(stub_fn, node)

        fn_outline = SymbolOutline(
            name=node.name,
            symbol_type=stype,
            signature=sig_line,
            docstring=condensed_doc,
            decorators=decorators,
            line_number=getattr(node, "lineno", None),
        )
        return fn_outline, stub_fn

    @staticmethod
    def _get_target_name(target: ast.AST) -> Optional[str]:
        """Extract identifier string from an assignment target."""
        if isinstance(target, ast.Name):
            return target.id
        return None


class GenericCodeCompressor:
    """Fallback regex-based compressor for non-Python or syntax-invalid source files."""

    CLASS_PATTERN = re.compile(
        r"^(?P<indent>\s*)(?:export\s+)?(?:public\s+|abstract\s+)?class\s+(?P<name>[A-Za-z0-9_]+)(?P<rest>[^{\n:]*)",
        re.MULTILINE,
    )
    FUNC_PATTERN = re.compile(
        r"^(?P<indent>\s*)(?:export\s+)?(?:async\s+)?(?:public\s+|static\s+|private\s+)?(?:def|function|fn|func)\s+(?P<name>[A-Za-z0-9_]+)(?P<sig>\([^)]*\)(?:\s*->\s*[^{:\n]+)?)",
        re.MULTILINE,
    )

    def compress(self, source_code: str, file_name: Optional[str] = None) -> Tuple[str, List[SymbolOutline]]:
        """Produce an outline using heuristic line and regex scanning."""
        lines = source_code.splitlines()
        symbols: List[SymbolOutline] = []
        outline_lines: List[str] = []

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith(("//", "#", "/*", "*")):
                continue

            # Class match
            c_match = self.CLASS_PATTERN.match(line)
            if c_match:
                name = c_match.group("name")
                rest = c_match.group("rest").strip()
                sig = f"class {name} {rest}".strip()
                symbols.append(SymbolOutline(name=name, symbol_type=SymbolType.CLASS, signature=sig, line_number=lineno))
                outline_lines.append(f"{c_match.group('indent')}class {name}{' ' + rest if rest else ''}: ...")
                continue

            # Function match
            f_match = self.FUNC_PATTERN.match(line)
            if f_match:
                name = f_match.group("name")
                sig = f"{name}{f_match.group('sig')}".strip()
                symbols.append(SymbolOutline(name=name, symbol_type=SymbolType.FUNCTION, signature=sig, line_number=lineno))
                outline_lines.append(f"{f_match.group('indent')}def {sig}: ...")
                continue

        outline_text = "\n".join(outline_lines) if outline_lines else "# [No top-level class or function signatures found]"
        return outline_text, symbols


def _prune_to_budget(
    raw_source: str,
    initial_summary: ContextSummary,
    max_tokens: int,
    file_name: Optional[str] = None,
) -> ContextSummary:
    """Progressively apply 4-tier degradation until output conforms to max_tokens ceiling."""
    current_tokens = initial_summary.stats.compressed_tokens_est
    if current_tokens <= max_tokens:
        return initial_summary

    # Tier 1: Strip docstrings entirely
    tier1_compressor = PythonASTCompressor(
        include_private=False,
        include_docstrings=False,
        max_docstring_lines=0,
    )
    try:
        t1_text, t1_symbols = tier1_compressor.compress(raw_source, file_name)
    except Exception:
        t1_text, t1_symbols = initial_summary.outline_text, initial_summary.symbols

    t1_tokens = estimate_tokens(t1_text)
    if t1_tokens <= max_tokens:
        orig_chars = len(raw_source)
        comp_chars = len(t1_text)
        stats = CompressionStats(
            original_chars=orig_chars,
            compressed_chars=comp_chars,
            original_tokens_est=estimate_tokens(raw_source),
            compressed_tokens_est=t1_tokens,
            compression_ratio=round(comp_chars / max(1, orig_chars), 3),
            tokens_saved_pct=round(max(0.0, 100.0 * (1.0 - (t1_tokens / max(1, estimate_tokens(raw_source))))), 1),
            symbol_count=len(t1_symbols),
        )
        return ContextSummary(outline_text=t1_text, symbols=t1_symbols, stats=stats, metadata=initial_summary.metadata)

    # Tier 2: Strip class attributes and keep only method signatures
    tier2_lines = []
    for line in t1_text.splitlines():
        # Keep class defs, function defs, and ellipses; drop variable assigns
        if line.startswith("class ") or line.startswith("def ") or line.startswith("async def ") or line.strip() == "...":
            tier2_lines.append(line)
        elif line.startswith("    def ") or line.startswith("    async def "):
            tier2_lines.append(line)
            tier2_lines.append("        ...")
    t2_text = "\n".join(tier2_lines)
    t2_tokens = estimate_tokens(t2_text)
    if t2_tokens <= max_tokens:
        orig_chars = len(raw_source)
        comp_chars = len(t2_text)
        stats = CompressionStats(
            original_chars=orig_chars,
            compressed_chars=comp_chars,
            original_tokens_est=estimate_tokens(raw_source),
            compressed_tokens_est=t2_tokens,
            compression_ratio=round(comp_chars / max(1, orig_chars), 3),
            tokens_saved_pct=round(max(0.0, 100.0 * (1.0 - (t2_tokens / max(1, estimate_tokens(raw_source))))), 1),
            symbol_count=len(t1_symbols),
        )
        return ContextSummary(outline_text=t2_text, symbols=t1_symbols, stats=stats, metadata=initial_summary.metadata)

    # Tier 3: Method collapsing (keep only class headers and count of methods)
    tier3_lines = []
    in_class = False
    methods_in_current_class = 0
    for line in t2_text.splitlines():
        if line.startswith("class "):
            if in_class and methods_in_current_class > 0:
                tier3_lines.append(f"    # +{methods_in_current_class} methods omitted for brevity")
            in_class = True
            methods_in_current_class = 0
            tier3_lines.append(line)
        elif in_class and (line.startswith("    def ") or line.startswith("    async def ")):
            if methods_in_current_class < 2:
                tier3_lines.append(line)
                tier3_lines.append("        ...")
            methods_in_current_class += 1
        elif not in_class:
            tier3_lines.append(line)

    if in_class and methods_in_current_class > 2:
        tier3_lines.append(f"    # +{methods_in_current_class - 2} additional methods omitted")

    t3_text = "\n".join(tier3_lines)
    t3_tokens = estimate_tokens(t3_text)
    if t3_tokens <= max_tokens:
        orig_chars = len(raw_source)
        comp_chars = len(t3_text)
        stats = CompressionStats(
            original_chars=orig_chars,
            compressed_chars=comp_chars,
            original_tokens_est=estimate_tokens(raw_source),
            compressed_tokens_est=t3_tokens,
            compression_ratio=round(comp_chars / max(1, orig_chars), 3),
            tokens_saved_pct=round(max(0.0, 100.0 * (1.0 - (t3_tokens / max(1, estimate_tokens(raw_source))))), 1),
            symbol_count=len(t1_symbols),
        )
        return ContextSummary(outline_text=t3_text, symbols=t1_symbols, stats=stats, metadata=initial_summary.metadata)

    # Tier 4: Hard character/token slice boundary with warning sentinel
    allowed_chars = max(100, (max_tokens * 4) - 80)
    truncated = t3_text[:allowed_chars]
    # Slice to last newline
    last_nl = truncated.rfind("\n")
    if last_nl > 50:
        truncated = truncated[:last_nl]
    t4_text = f"{truncated}\n# [... Truncated: exceeded budget of {max_tokens} tokens ...]"
    t4_tokens = estimate_tokens(t4_text)
    orig_chars = len(raw_source)
    comp_chars = len(t4_text)
    stats = CompressionStats(
        original_chars=orig_chars,
        compressed_chars=comp_chars,
        original_tokens_est=estimate_tokens(raw_source),
        compressed_tokens_est=t4_tokens,
        compression_ratio=round(comp_chars / max(1, orig_chars), 3),
        tokens_saved_pct=round(max(0.0, 100.0 * (1.0 - (t4_tokens / max(1, estimate_tokens(raw_source))))), 1),
        symbol_count=len(t1_symbols),
    )
    return ContextSummary(outline_text=t4_text, symbols=t1_symbols, stats=stats, metadata=initial_summary.metadata)


def _render_markdown_outline(summary: ContextSummary, file_label: Optional[str] = None) -> str:
    """Format symbol tree into clean GitHub Markdown outline."""
    lines = []
    title = file_label or "Module Symbol Outline"
    lines.append(f"## 📋 {title}")
    lines.append(
        f"**Compression:** {summary.stats.compressed_tokens_est} tokens "
        f"({summary.stats.tokens_saved_pct:.1f}% reduction, {summary.stats.symbol_count} symbols)"
    )
    lines.append("")

    for sym in summary.symbols:
        icon = "🏛️" if sym.symbol_type == SymbolType.CLASS else "⚡"
        lines.append(f"### {icon} `{sym.name}` ({sym.symbol_type.value})")
        if sym.signature:
            lines.append("```python")
            lines.append(sym.signature)
            lines.append("```")
        if sym.docstring:
            lines.append(f"> {sym.docstring}")
        if sym.children:
            lines.append("")
            lines.append("**Members & Methods:**")
            for child in sym.children:
                c_icon = "🔹" if child.symbol_type == SymbolType.VARIABLE else "🔸"
                c_sig = child.signature or child.name
                lines.append(f"- {c_icon} `{c_sig}`" + (f" — *{child.docstring}*" if child.docstring else ""))
        lines.append("")
    return "\n".join(lines).strip()


def summarize_context(
    source: Union[str, Path, List[Union[str, Path]], Dict[str, str]],
    *,
    max_tokens: Optional[int] = None,
    include_private: bool = False,
    include_docstrings: bool = True,
    max_docstring_lines: int = 1,
    include_imports: bool = False,
    output_format: str = "stub",
    language: Optional[str] = None,
) -> ContextSummary:
    """Produce concise symbol outlines, key signatures, and interfaces for inter-agent handoffs.

    Args:
        source: Source code string, Path to a file, list of Paths/strings, or dict of {filename: content}.
        max_tokens: Optional token ceiling enforcing 4-tier adaptive compression.
        include_private: Whether to include private symbols starting with '_' (default False).
        include_docstrings: Whether to include condensed docstrings (default True).
        max_docstring_lines: Maximum lines retained per docstring (default 1).
        include_imports: Whether to preserve import statements in outline (default False).
        output_format: Output format: 'stub' (.pyi style), 'markdown', or 'json' (default 'stub').
        language: Language hint ('python' or 'generic'); auto-detected if None.

    Returns:
        ContextSummary containing formatted outline text, symbol list, and compression metrics.
    """
    # 1. Multi-file Dict or List Handling
    if isinstance(source, dict):
        return _summarize_multiple_sources(
            source,
            max_tokens=max_tokens,
            include_private=include_private,
            include_docstrings=include_docstrings,
            max_docstring_lines=max_docstring_lines,
            include_imports=include_imports,
            output_format=output_format,
            language=language,
        )

    if isinstance(source, list):
        sources_dict: Dict[str, str] = {}
        for idx, item in enumerate(source):
            if isinstance(item, (str, Path)) and Path(str(item)).is_file():
                p = Path(str(item))
                sources_dict[p.as_posix()] = p.read_text(encoding="utf-8", errors="replace")
            else:
                sources_dict[f"source_{idx + 1}.py"] = str(item)
        return _summarize_multiple_sources(
            sources_dict,
            max_tokens=max_tokens,
            include_private=include_private,
            include_docstrings=include_docstrings,
            max_docstring_lines=max_docstring_lines,
            include_imports=include_imports,
            output_format=output_format,
            language=language,
        )

    # 2. Single File Path Handling
    file_name: Optional[str] = None
    if isinstance(source, Path) or (isinstance(source, str) and "\n" not in source and Path(source).is_file()):
        p = Path(source)
        file_name = p.as_posix()
        source_text = p.read_text(encoding="utf-8", errors="replace")
    else:
        source_text = str(source)
        file_name = "<inline_source>"

    # 3. Detection of language and parser selection
    is_python = (
        language == "python"
        or (file_name and file_name.endswith((".py", ".pyi")))
        or (language is None and "\n" in source_text and "def " in source_text or "class " in source_text)
    )

    symbols: List[SymbolOutline] = []
    outline_text: str = ""

    if is_python:
        try:
            compressor = PythonASTCompressor(
                include_private=include_private,
                include_docstrings=include_docstrings,
                max_docstring_lines=max_docstring_lines,
                include_imports=include_imports,
            )
            outline_text, symbols = compressor.compress(source_text, file_name=file_name)
        except SyntaxError:
            # Fallback to generic regex compressor on syntax error
            fallback = GenericCodeCompressor()
            outline_text, symbols = fallback.compress(source_text, file_name=file_name)
    else:
        fallback = GenericCodeCompressor()
        outline_text, symbols = fallback.compress(source_text, file_name=file_name)

    orig_chars = len(source_text)
    comp_chars = len(outline_text)
    orig_tokens = estimate_tokens(source_text)
    comp_tokens = estimate_tokens(outline_text)

    stats = CompressionStats(
        original_chars=orig_chars,
        compressed_chars=comp_chars,
        original_tokens_est=orig_tokens,
        compressed_tokens_est=comp_tokens,
        compression_ratio=round(comp_chars / max(1, orig_chars), 3),
        tokens_saved_pct=round(max(0.0, 100.0 * (1.0 - (comp_tokens / max(1, orig_tokens)))), 1),
        symbol_count=len(symbols),
    )

    summary = ContextSummary(
        outline_text=outline_text,
        symbols=symbols,
        stats=stats,
        metadata={"file": file_name, "format": output_format},
    )

    # 4. Budget Enforcement
    if max_tokens is not None and summary.stats.compressed_tokens_est > max_tokens:
        summary = _prune_to_budget(source_text, summary, max_tokens, file_name=file_name)

    # 5. Output Format Conversion
    if output_format.lower() == "markdown":
        summary.outline_text = _render_markdown_outline(summary, file_label=file_name)
    elif output_format.lower() == "json":
        summary.outline_text = json.dumps(summary.to_dict(), indent=2)

    return summary


def _summarize_multiple_sources(
    sources: Dict[str, str],
    *,
    max_tokens: Optional[int] = None,
    include_private: bool = False,
    include_docstrings: bool = True,
    max_docstring_lines: int = 1,
    include_imports: bool = False,
    output_format: str = "stub",
    language: Optional[str] = None,
) -> ContextSummary:
    """Summarize multiple files and aggregate them into a composite handoff summary."""
    summaries: List[ContextSummary] = []
    total_orig_chars = 0
    total_comp_chars = 0
    total_symbols: List[SymbolOutline] = []
    sections: List[str] = []

    # Calculate per-file token budget if max_tokens given
    per_file_budget = (max_tokens // max(1, len(sources))) if max_tokens else None

    for fname, content in sources.items():
        file_summary = summarize_context(
            content,
            max_tokens=per_file_budget,
            include_private=include_private,
            include_docstrings=include_docstrings,
            max_docstring_lines=max_docstring_lines,
            include_imports=include_imports,
            output_format="stub",
            language=language,
        )
        file_summary.metadata["file"] = fname
        summaries.append(file_summary)
        total_orig_chars += len(content)
        total_comp_chars += len(file_summary.outline_text)
        total_symbols.extend(file_summary.symbols)

        header = (
            f"# ==============================================================================\n"
            f"# File: {fname} ({file_summary.stats.original_tokens_est} tok -> "
            f"{file_summary.stats.compressed_tokens_est} tok | {file_summary.stats.tokens_saved_pct:.1f}% saved)\n"
            f"# =============================================================================="
        )
        sections.append(f"{header}\n{file_summary.outline_text}\n")

    composite_text = "\n".join(sections)
    comp_tokens = estimate_tokens(composite_text)
    orig_tokens = estimate_tokens("".join(sources.values()))

    stats = CompressionStats(
        original_chars=total_orig_chars,
        compressed_chars=len(composite_text),
        original_tokens_est=orig_tokens,
        compressed_tokens_est=comp_tokens,
        compression_ratio=round(len(composite_text) / max(1, total_orig_chars), 3),
        tokens_saved_pct=round(max(0.0, 100.0 * (1.0 - (comp_tokens / max(1, orig_tokens)))), 1),
        symbol_count=len(total_symbols),
    )

    composite_summary = ContextSummary(
        outline_text=composite_text,
        symbols=total_symbols,
        stats=stats,
        metadata={"file_count": len(sources), "files": list(sources.keys())},
    )

    if max_tokens is not None and composite_summary.stats.compressed_tokens_est > max_tokens:
        composite_summary = _prune_to_budget(
            "".join(sources.values()),
            composite_summary,
            max_tokens,
            file_name="composite_bundle",
        )

    if output_format.lower() == "markdown":
        composite_summary.outline_text = _render_markdown_outline(composite_summary, file_label="Multi-File Bundle")
    elif output_format.lower() == "json":
        composite_summary.outline_text = json.dumps(composite_summary.to_dict(), indent=2)

    return composite_summary


def summarize_file(path: Union[str, Path], **kwargs: Any) -> ContextSummary:
    """Convenience helper to summarize a single file from disk."""
    return summarize_context(Path(path), **kwargs)


def summarize_directory(
    dir_path: Union[str, Path],
    glob_pattern: str = "*.py",
    recursive: bool = True,
    **kwargs: Any,
) -> ContextSummary:
    """Scan and summarize an entire directory matching a glob pattern."""
    target_dir = Path(dir_path)
    if not target_dir.is_dir():
        raise NotADirectoryError(f"Target path '{dir_path}' is not a directory.")

    files = list(target_dir.rglob(glob_pattern) if recursive else target_dir.glob(glob_pattern))
    sources: Dict[str, str] = {}
    for f in sorted(files):
        if f.is_file():
            sources[f.relative_to(target_dir).as_posix()] = f.read_text(encoding="utf-8", errors="replace")

    return summarize_context(sources, **kwargs)


def format_for_handoff(summary: ContextSummary, task_objective: Optional[str] = None) -> str:
    """Wrap summary into a structured prompt block ready for inter-agent delegation."""
    header = "### 🤝 INTER-AGENT CONTEXT HANDOFF"
    if task_objective:
        header += f"\n**Objective:** {task_objective}"
    meta = (
        f"**Context Compression:** {summary.stats.compressed_tokens_est} tokens "
        f"({summary.stats.tokens_saved_pct:.1f}% reduction, {summary.stats.symbol_count} symbols preserved)"
    )
    return f"{header}\n{meta}\n\n```python\n{summary.outline_text}\n```"
