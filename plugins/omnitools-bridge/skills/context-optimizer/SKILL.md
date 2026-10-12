---
name: context-optimizer
description: >-
  Manage LLM token budgets, compress AST trees and unified diffs, and maintain
  in-memory indexes for maximum context efficiency during heavy coding workflows.
---

# Context Optimizer Skill

The `context-optimizer` skill guarantees token-efficient agent operation across large codebases.

## Features
- **Budget Management (`budget.py`)**: Tracks prompt/completion token usage and dynamically trims verbose contexts.
- **Context Compression (`compressor.py`)**: Strips unnecessary docstrings, comments, whitespace, and compacts code outlines without losing structural AST fidelity.
- **Fast Indexing (`indexer.py`)**: In-memory caching and indexing of project symbols to prevent redundant file scans.
