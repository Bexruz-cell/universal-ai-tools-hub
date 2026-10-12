---
name: test-runner
description: >-
  Autonomous test verification gate: compiles modified Python files using py_compile,
  resolves affected test targets, and executes targeted pytest suites.
---

# Test Runner & Verification Gate Skill

The `test-runner` skill establishes an automated verification protocol for autonomous agents modifying codebases.

## Features
- **Compilation Gate**: Pre-validates syntax across Python files via `python -m py_compile` to catch syntax errors immediately.
- **Affected Target Resolution**: Analyzes import dependencies and file naming conventions to run only tests related to changed code.
- **Detailed Diagnostics**: Captures failure summaries, tracebacks, and assertion differences.

## Usage Example
```python
from src.coding_tools.test_runner import verify_changes

result = verify_changes(changed_files=["src/core/tools.py"], run_tests=True)
if not result.all_passed:
    print("Verification failed:", result.errors)
```
