---
name: git-checkpoints
description: >-
  Manage transient Git snapshots, inspect working tree diffs, create safety tags/branches,
  and perform instant rollbacks during multi-phase refactoring.
---

# Git Checkpoints & Rollback Skill

The `git-checkpoints` skill enables agentic workflows to save state before dangerous operations and roll back instantly if tests or verifications fail.

## Features
- **Instant Snapshots**: Save the exact repository state using lightweight Git refs or commits.
- **Diff Inspection**: Inspect changes between checkpoints or against HEAD before applying final commits.
- **Safe Rollback**: Discard uncommitted changes or revert to any prior checkpoint cleanly.

## Usage Example
```python
from src.coding_tools.checkpoints import git_create_checkpoint, git_rollback

cp = git_create_checkpoint(name="checkpoint-1")
# perform experimental modifications
git_rollback(cp["checkpoint_id"])
```
