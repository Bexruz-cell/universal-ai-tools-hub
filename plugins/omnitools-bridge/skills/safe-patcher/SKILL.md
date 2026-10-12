---
name: safe-patcher
description: >-
  Surgically apply code edits, regex replacements, and unified diffs with atomic backup,
  AST syntax validation, and automated rollback upon syntax errors.
---

# Safe Patcher Skill

The `safe-patcher` skill provides zero-risk code manipulation for autonomous agents.

## Features
- **Proposal Phase**: Generates standard unified diff previews before modifying any files.
- **Safety Backups**: Creates temporary `.bak` files prior to file modifications.
- **Atomic Replacement**: Writes via temporary files and atomic rename operations.
- **Syntax Verification**: Performs post-patch AST compilation checks with automatic instant rollback if syntax errors occur.
- **Workspace Sandboxing**: Strictly confines file operations within the workspace root.

## Usage Example
```python
from src.coding_tools.patcher import SafePatcher

patcher = SafePatcher(workspace_root=".")
proposal = patcher.propose_patch("src/core/tools.py", target="foo = 1", replacement="foo = 2")
patcher.apply_patch(proposal.patch_id, confirmed=True)
```
