---
name: security-guard
description: >-
  Workspace containment and execution security: enforces path boundaries, protects against directory
  traversal and symlink escapes, blocks dangerous DOS device names, and guards terminal commands.
---

# Security Guard Skill

The `security-guard` skill prevents accidental or malicious workspace escapes and destructive system actions.

## Security Layers
1. **Path Boundary Guard (`src.security.path_guard`)**:
   - Canonicalizes file paths and verifies strict containment within authorized workspace roots.
   - Detects and rejects traversal patterns (`..`, null bytes).
   - Rejects Windows-specific reserved DOS device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`).
   - Mitigates symlink redirection vulnerabilities.

2. **Command Guard (`src.security.command_guard`)**:
   - Intercepts shell commands to prevent destructive invocations (`rm -rf /`, `del /s /q C:\*`).
   - Restricts unvetted network calls and process execution outside the defined task scope.
