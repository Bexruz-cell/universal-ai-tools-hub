"""MCP Protocol Test Suite

Tests Model Context Protocol stdio server request/response JSON-RPC messages.
"""

import asyncio
import json
import subprocess
import sys
import pytest
from src.adapters.mcp_adapter import handle_call_tool, TOOLS


@pytest.mark.asyncio
async def test_mcp_handle_call_calc():
    res_str = await handle_call_tool("calc_expression", {"expression": "100 / 4"})
    res = json.loads(res_str)
    assert res["result"] == 25.0


@pytest.mark.asyncio
async def test_mcp_handle_call_search():
    res_str = await handle_call_tool("search_catalog", {"query": "langgraph"})
    res = json.loads(res_str)
    assert isinstance(res, list)
    assert len(res) > 0


@pytest.mark.asyncio
async def test_mcp_handle_call_unknown():
    res_str = await handle_call_tool("nonexistent_tool", {})
    assert "error" in res_str


def test_mcp_tools_list_schema():
    assert len(TOOLS) >= 5
    tool_names = [t["name"] for t in TOOLS]
    assert "deep_search" in tool_names
    assert "scrape_web" in tool_names
    assert "youtube_transcript" in tool_names
    assert "calc_expression" in tool_names
    assert "crypto_price" in tool_names

    for t in TOOLS:
        assert "name" in t
        assert "description" in t
        assert "inputSchema" in t
        assert t["inputSchema"]["type"] == "object"


def test_mcp_subprocess_stdio_handshake():
    """Test actual stdio subprocess handshake with mcp_adapter.py."""
    proc = subprocess.Popen(
        [sys.executable, "src/adapters/mcp_adapter.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8"
    )

    init_req = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) + "\n"
    stdout, _ = proc.communicate(input=init_req, timeout=5.0)

    assert proc.returncode == 0
    resp = json.loads(stdout.strip())
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert "protocolVersion" in resp["result"]
    assert resp["result"]["protocolVersion"] == "2024-11-05"
    assert "serverInfo" in resp["result"]
