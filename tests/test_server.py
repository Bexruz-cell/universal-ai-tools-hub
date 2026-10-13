import pytest
import asyncio
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.adapters.api_adapter import app
from src.core.tools import search_catalog_2026, convert_fiat
from src.adapters.mcp_adapter import handle_call_tool

client = TestClient(app)

def test_api_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "supported_ecosystems" in data
    assert "Claude (MCP)" in data["supported_ecosystems"]

def test_api_ai_plugin_manifest():
    response = client.get("/.well-known/ai-plugin.json")
    assert response.status_code == 200
    data = response.json()
    assert data["schema_version"] == "v1"
    assert data["name_for_model"] == "omnitools_superhub"

def test_catalog_2026():
    items = search_catalog_2026()
    assert len(items) == 50
    # Check specific 2026 repos
    names = [i["name"].lower() for i in items]
    assert any("firecrawl" in n for n in names)
    assert any("langgraph" in n for n in names)
    assert any("litellm" in n for n in names)

def test_catalog_search():
    items = search_catalog_2026(query="telegram")
    assert len(items) > 0
    assert any("telegram" in i["name"].lower() or "telegram" in i["use_case"].lower() for i in items)

def test_finance_convert_same_currency():
    response = client.get("/api/v1/finance/convert?amount=100&from_curr=USD&to_curr=USD")
    assert response.status_code == 200
    data = response.json()
    assert data["converted"] == 100.0
    assert data["rate"] == 1.0


def test_mcp_tool_handler():
    # Test MCP tool calling logic
    res = asyncio.run(handle_call_tool("search_catalog", {"query": "n8n", "limit": 5}))
    assert "n8n" in res.lower()
    
    res_curr = asyncio.run(handle_call_tool("convert_currency", {"amount": 50, "from_curr": "EUR", "to_curr": "EUR"}))
    assert "50" in res_curr
