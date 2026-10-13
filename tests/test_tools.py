"""Functional Test Suite: Core Tools Engine

Tests mathematical calculations, web scraping, search, and 2026 catalog operations.
"""

import pytest
from src.core.tools import (
    calc_expression,
    convert_fiat,
    deep_search,
    search_catalog_2026,
)


def test_calc_expression_valid_arithmetic():
    res = calc_expression("10 * 5 + 3")
    assert res["result"] == 53.0

    res2 = calc_expression("(100 - 20) / 4")
    assert res2["result"] == 20.0

    res3 = calc_expression("sqrt(144) + 12")
    assert res3["result"] == 24.0

    res4 = calc_expression("2 ** 8")
    assert res4["result"] == 256.0


def test_calc_expression_division_by_zero():
    res = calc_expression("10 / 0")
    assert "error" in res
    assert "Division by zero" in res["error"]


def test_calc_expression_disallowed_code_injection():
    res = calc_expression("__import__('os').system('dir')")
    assert "error" in res
    assert "Disallowed" in res["error"] or "Invalid" in res["error"]


def test_search_catalog_2026():
    items = search_catalog_2026()
    assert len(items) == 50
    names = [i["name"].lower() for i in items]
    assert any("firecrawl" in n for n in names)
    assert any("langgraph" in n for n in names)
    assert any("litellm" in n for n in names)


def test_search_catalog_filter():
    items = search_catalog_2026(query="telegram")
    assert len(items) > 0
    assert any("telegram" in i["name"].lower() or "telegram" in i.get("description", "").lower() for i in items)


@pytest.mark.asyncio
async def test_deep_search_query():
    res = await deep_search(query="MCP", num_results=3)
    assert "results" in res
    assert len(res["results"]) > 0


@pytest.mark.asyncio
async def test_convert_fiat_same_currency():
    res = await convert_fiat(100.0, "USD", "USD")
    assert res["converted"] == 100.0
    assert res["rate"] == 1.0
