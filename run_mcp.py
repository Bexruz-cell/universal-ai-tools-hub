"""Portable launcher for OmniTools Model Context Protocol (MCP) Stdio Server.

Compatible with Claude Desktop, OpenAI Codex, and Google Antigravity.
Ensures UTF-8 encoding across Windows, macOS, and Linux stdio transports.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Configure UTF-8 encoding for stdio streams
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

# Dynamically ensure root and src are on sys.path
root_dir = Path(__file__).resolve().parent
src_dir = root_dir / "src"

if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
if src_dir.exists() and str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

if __name__ == "__main__":
    from src.adapters.mcp_adapter import main
    main()
