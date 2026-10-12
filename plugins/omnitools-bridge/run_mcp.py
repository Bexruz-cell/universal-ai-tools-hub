"""Portable standalone entrypoint for OmniTools MCP server.

Automatically resolves paths and runs whether executed inside the repository
or when cached by Codex in ~/.codex/plugins/cache/...
"""

import os
import sys
from pathlib import Path

# Configure UTF-8 encoding for stdio
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

plugin_dir = Path(__file__).resolve().parent

# Check local src/ within plugin directory (when cached standalone)
local_src = plugin_dir / "src"
if local_src.exists():
    sys.path.insert(0, str(plugin_dir))
    sys.path.insert(0, str(local_src))

# Check parent repository root (when run in-tree)
repo_root = plugin_dir.parent.parent
if (repo_root / "src").exists():
    sys.path.insert(0, str(repo_root))

try:
    from src.adapters.mcp_adapter import main
    main()
except ImportError:
    # Direct relative import fallback
    try:
        from adapters.mcp_adapter import main
        main()
    except Exception as e:
        sys.stderr.write(f"Failed to start OmniTools MCP server: {e}\n")
        sys.exit(1)
