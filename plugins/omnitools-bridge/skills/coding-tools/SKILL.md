---
name: coding-tools
description: >-
  Comprehensive suite of 15 autonomous coding and software engineering tools for AI agents.
  Includes safe patch engine, test runner, AST search, symbol extraction, repo map generator,
  dependency graph, Git checkpoints with instant rollback, traceback diagnostics, context
  budget & compression, and workspace security guards.
---

# 15 Autonomous Coding Tools Suite

The `coding-tools` skill provides a production-grade autonomous software engineering framework designed for OpenAI Codex, Google Antigravity, and Anthropic Claude agents.

## Core Capabilities & Tool Matrix

| # | Tool Name | Module | Primary Capability |
|---|---|---|---|
| 1 | **Safe Patcher** | `src.coding_tools.patcher` | Unified diff generation, AST syntax validation, atomic writes, auto-rollback |
| 2 | **Test Runner** | `src.coding_tools.test_runner` | Targeted pytest execution, `py_compile` checks, automated verification gates |
| 3 | **Symbol Analyzer** | `src.coding_tools.symbols` | AST extraction of classes, functions, methods, docstrings, and signatures |
| 4 | **AST Search** | `src.coding_tools.search` | Semantic and structural search across python abstract syntax trees |
| 5 | **Repo Map** | `src.coding_tools.repo_map` | High-density codebase structure visualizer and hierarchical symbol map |
| 6 | **Dependency Graph** | `src.coding_tools.deps` | Computes dependency relations, import chains, and affected test targets |
| 7 | **Git Checkpoints** | `src.coding_tools.checkpoints` | Instant snapshot tagging, dirty-tree tracking, and zero-loss rollback |
| 8 | **Traceback Diagnostics** | `src.coding_tools.diagnostics` | Parses Python tracebacks, pinpoints root failure lines, suggests remedies |
| 9 | **Docs Search** | `src.coding_tools.docs` | Curated documentation search across standard libraries and frameworks |
| 10 | **Context Budget** | `src.context_optimizer.budget` | Token budget accounting across multi-turn LLM reasoning contexts |
| 11 | **Context Compressor** | `src.context_optimizer.compressor` | AST tree compression, comment stripping, and diff minimizing |
| 12 | **Codebase Indexer** | `src.context_optimizer.indexer` | High-speed in-memory indexing of repository symbols and references |
| 13 | **Path Guard** | `src.security.path_guard` | Traversal containment, DOS reserved name sanitization, symlink escape defense |
| 14 | **Command Guard** | `src.security.command_guard` | Dangerous command blocking (rm -rf, fork bombs, unauthorized network callers) |
| 15 | **Coding Catalog** | `src.coding_tools.catalog` | Curated search engine across the 2026 Top-50 Open-Source Coding Repositories |

## Usage Runbook

### 1. Verification Gate Before Applying Changes
Always invoke the test runner and syntax compiler before and after making code changes:
```python
from src.coding_tools.test_runner import verify_changes

result = verify_changes(
    changed_files=["src/core/tools.py"],
    run_tests=True
)
print("Passed:", result.all_passed)
```

### 2. Surgical Code Patching with Auto-Rollback
```python
from src.coding_tools.patcher import SafePatcher

patcher = SafePatcher(workspace_root=".")
proposal = patcher.propose_patch(file_path="src/example.py", target="old_func()", replacement="new_func()")
print(proposal.diff)
patcher.apply_patch(proposal.patch_id, confirmed=True)
```

### 3. Safe Git Checkpointing
```python
from src.coding_tools.checkpoints import git_create_checkpoint, git_rollback

cp = git_create_checkpoint(name="pre-refactor-feature-x")
# Make modifications...
# If tests fail, restore instantly:
git_rollback(cp["checkpoint_id"])
```
