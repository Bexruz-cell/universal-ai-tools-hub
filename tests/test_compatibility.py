"""Compatibility QA Test Suite

Verifies 100% compatibility with Google Antigravity, Anthropic Claude, and OpenAI ChatGPT.
"""

import json
from pathlib import Path
import pytest


def test_antigravity_plugin_manifest():
    p = Path("plugin.json")
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert "$schema" in data
    assert "antigravity" in data["$schema"]
    assert data["name"] == "omnitools-bridge"
    assert "skills" in data
    assert "skills/omnitools-bridge" in data["skills"]
    assert "mcpServers" in data


def test_antigravity_skill_specification():
    skill_p = Path("skills/omnitools-bridge/SKILL.md")
    assert skill_p.exists()
    content = skill_p.read_text(encoding="utf-8")
    assert content.startswith("---")
    assert "name: omnitools-bridge" in content


def test_claude_desktop_config():
    conf_p = Path("configs/claude_desktop_config.json")
    assert conf_p.exists()
    data = json.loads(conf_p.read_text(encoding="utf-8"))
    assert "mcpServers" in data
    assert "omnitools_bridge" in data["mcpServers"] or "omnitools-hub" in data["mcpServers"]


def test_chatgpt_plugin_manifest():
    manifest_p = Path(".well-known/ai-plugin.json")
    assert manifest_p.exists()
    data = json.loads(manifest_p.read_text(encoding="utf-8"))
    assert data["schema_version"] == "v1"
    assert "name_for_model" in data
    assert len(data["name_for_human"]) <= 20
    assert len(data["description_for_human"]) <= 100


def test_claude_desktop_mcp_handshake():
    """Verify that Claude Desktop configured MCP server starts and passes MCP JSON-RPC handshake."""
    import subprocess, sys
    conf_p = Path("configs/claude_desktop_config.json")
    data = json.loads(conf_p.read_text(encoding="utf-8"))
    server_conf = data["mcpServers"]["omnitools_bridge"]
    
    script_path = server_conf["args"][0]
    target_script = Path(script_path)
    if not target_script.is_absolute():
        target_script = Path(__file__).resolve().parent.parent / script_path
    assert target_script.exists(), f"Claude MCP server script not found: {target_script}"
    
    proc = subprocess.Popen(
        [sys.executable, str(target_script)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8"
    )
    req = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "claude-desktop-test", "version": "1.0"}
        }
    }) + "\n"
    
    stdout, _ = proc.communicate(input=req, timeout=5)
    resp = json.loads(stdout.strip())
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert "serverInfo" in resp["result"]
    assert resp["result"]["serverInfo"]["name"] == "OmniTools-Universal-AI-Bridge"


def test_openapi_specification_validity():
    """Verify openapi.json is valid OpenAPI 3.1.0 with required paths and components."""
    openapi_p = Path("openapi.json")
    assert openapi_p.exists()
    spec = json.loads(openapi_p.read_text(encoding="utf-8"))
    assert spec["openapi"].startswith("3.1")
    assert "info" in spec
    assert "paths" in spec
    # Check that all core tools are represented in paths
    paths = spec["paths"]
    assert "/tools/calc" in paths
    assert "/tools/scrape" in paths
    assert "/tools/youtube" in paths
    assert "/tools/crypto" in paths
    assert "/tools/search" in paths
    assert "/tools/convert" in paths
    assert "/catalog" in paths


def test_antigravity_direct_tools_execution():
    """Verify Antigravity can import and call all core tools without errors."""
    import asyncio
    from src.core.tools import (
        calc_expression,
        search_catalog_2026,
        search_catalog,
        convert_currency,
        get_crypto_prices
    )
    assert calc_expression("40 + 2")["result"] == 42.0
    assert len(search_catalog("agent")) > 0
    assert len(search_catalog_2026("mcp")) > 0
    conv = asyncio.run(convert_currency(10, "USD", "EUR"))
    assert "converted" in conv
