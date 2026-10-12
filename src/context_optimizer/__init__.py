"""OmniTools Universal AI Bridge - Context Optimizer

Provides context compression, symbol outlines, and token budget management
for efficient inter-agent handoffs.
"""

from src.context_optimizer.compressor import (
    ContextSummary,
    CompressionStats,
    SymbolOutline,
    SymbolType,
    summarize_context,
    summarize_file,
    summarize_directory,
    format_for_handoff,
)

__all__ = [
    "ContextSummary",
    "CompressionStats",
    "SymbolOutline",
    "SymbolType",
    "summarize_context",
    "summarize_file",
    "summarize_directory",
    "format_for_handoff",
]
