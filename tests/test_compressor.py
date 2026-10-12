"""Unit Tests for Context Compression Engine (src/context_optimizer/compressor.py)."""

import json
from pathlib import Path
import pytest

from src.context_optimizer.compressor import (
    ContextSummary,
    CompressionStats,
    SymbolOutline,
    SymbolType,
    summarize_context,
    summarize_file,
    summarize_directory,
    format_for_handoff,
    estimate_tokens,
)

SAMPLE_PYTHON_CODE = '''"""Sample module for testing context compression."""

import os
from typing import Dict, List, Optional, Any

API_VERSION = "2.0.0"
MAX_RETRIES = 5
_SECRET_KEY = "internal_secret"

class EngineConfig:
    """Configuration settings for execution engine."""
    timeout: int = 30
    retries: int = 3

    def __init__(self, host: str, port: int = 8080) -> None:
        """Initialize configuration with network host and port."""
        self.host = host
        self.port = port
        self._private_state = "hidden"

    def get_endpoint(self) -> str:
        """Return formatted connection URI string."""
        return f"http://{self.host}:{self.port}"

    def _internal_helper(self) -> None:
        """Private helper function."""
        pass


def execute_pipeline(config: EngineConfig, payload: Dict[str, Any], dry_run: bool = False) -> bool:
    """Execute end-to-end data processing pipeline."""
    # Verbose implementation that should be stripped
    for i in range(100):
        print("processing", i)
    return True


async def fetch_async_data(url: str, timeout: float = 10.0) -> Optional[str]:
    """Asynchronously fetch contents from remote URL."""
    # Another long implementation
    return "result"


def _hidden_utility() -> None:
    """This function is private and should be omitted by default."""
    print("hidden")
'''


def test_compress_python_code_stubs():
    summary = summarize_context(SAMPLE_PYTHON_CODE, include_private=False)
    assert isinstance(summary, ContextSummary)
    assert summary.stats.original_tokens_est > summary.stats.compressed_tokens_est
    assert summary.stats.tokens_saved_pct > 30.0

    outline = summary.outline_text
    # Public symbols present
    assert "class EngineConfig" in outline
    assert "def __init__(self, host: str, port: int=8080) -> None:" in outline or "port: int = 8080" in outline
    assert "def get_endpoint(self) -> str:" in outline
    assert "def execute_pipeline(" in outline
    assert "async def fetch_async_data(" in outline
    assert "API_VERSION" in outline

    # Private symbols excluded
    assert "_hidden_utility" not in outline
    assert "_internal_helper" not in outline
    assert "_SECRET_KEY" not in outline

    # Bodies replaced with ...
    assert "for i in range(100)" not in outline
    assert "..." in outline


def test_symbol_hierarchy():
    summary = summarize_context(SAMPLE_PYTHON_CODE, include_private=False)
    symbol_names = [s.name for s in summary.symbols]
    assert "EngineConfig" in symbol_names
    assert "execute_pipeline" in symbol_names
    assert "fetch_async_data" in symbol_names

    cls_sym = next(s for s in summary.symbols if s.name == "EngineConfig")
    assert cls_sym.symbol_type == SymbolType.CLASS
    child_names = [c.name for c in cls_sym.children]
    assert "__init__" in child_names
    assert "get_endpoint" in child_names
    assert "_internal_helper" not in child_names


def test_include_private_symbols():
    summary = summarize_context(SAMPLE_PYTHON_CODE, include_private=True)
    outline = summary.outline_text
    assert "_hidden_utility" in outline
    assert "_internal_helper" in outline


def test_docstring_handling():
    # Test with docstrings
    summary_with_doc = summarize_context(SAMPLE_PYTHON_CODE, include_docstrings=True)
    assert "Execute end-to-end data processing pipeline." in summary_with_doc.outline_text

    # Test without docstrings
    summary_no_doc = summarize_context(SAMPLE_PYTHON_CODE, include_docstrings=False)
    assert "Execute end-to-end data processing pipeline." not in summary_no_doc.outline_text
    assert summary_no_doc.stats.compressed_tokens_est <= summary_with_doc.stats.compressed_tokens_est


def test_max_tokens_budget_pruning():
    summary = summarize_context(SAMPLE_PYTHON_CODE, max_tokens=60)
    assert summary.stats.compressed_tokens_est <= 75


def test_output_formats():
    # Markdown
    md_summary = summarize_context(SAMPLE_PYTHON_CODE, output_format="markdown")
    assert md_summary.outline_text.startswith("## 📋")
    assert "### 🏛️ `EngineConfig`" in md_summary.outline_text

    # JSON
    json_summary = summarize_context(SAMPLE_PYTHON_CODE, output_format="json")
    data = json.loads(json_summary.outline_text)
    assert "outline_text" in data
    assert "symbols" in data
    assert "stats" in data
    assert data["stats"]["symbol_count"] > 0


def test_syntax_error_fallback():
    malformed_code = """
    class BrokenSyntax
        def my_broken_fn(x, y):
            invalid python syntax { [
    """
    summary = summarize_context(malformed_code, language="generic")
    assert summary is not None
    assert summary.stats.symbol_count >= 0


def test_multi_source_dict():
    sources = {
        "module_a.py": "def add(x: int, y: int) -> int:\n    return x + y\n",
        "module_b.py": "class Worker:\n    def run(self) -> None:\n        print('running')\n",
    }
    summary = summarize_context(sources)
    assert "module_a.py" in summary.outline_text
    assert "module_b.py" in summary.outline_text
    assert "def add(x: int, y: int) -> int:" in summary.outline_text
    assert "class Worker:" in summary.outline_text


def test_format_for_handoff():
    summary = summarize_context("def foo() -> None:\n    pass\n")
    handoff_text = format_for_handoff(summary, task_objective="Implement consumer module")
    assert "INTER-AGENT CONTEXT HANDOFF" in handoff_text
    assert "Implement consumer module" in handoff_text
    assert "def foo() -> None:" in handoff_text
