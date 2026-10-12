"""Comprehensive REST API Test Suite for OmniTools Universal Hub.

Verifies HTTP status codes, JSON schema conformity, SSRF rejection, and error formatting.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from src.adapters.api_adapter import app

client = TestClient(app)


def test_root_get_success():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "supported_ecosystems" in data


def test_root_method_not_allowed():
    response = client.post("/", json={"ping": "pong"})
    assert response.status_code == 405


@pytest.mark.parametrize("payload,expected_result", [
    ({"expression": "2 + 2"}, 4.0),
    ({"expression": "10 * 5 + 3"}, 53.0),
    ({"expression": "(100 - 20) / 4"}, 20.0),
    ({"expression": "2 ** 3"}, 8.0),
])
def test_calc_valid_expressions(payload, expected_result):
    response = client.post("/tools/calc", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    assert float(data["result"]) == pytest.approx(expected_result)


def test_calc_division_by_zero():
    response = client.post("/tools/calc", json={"expression": "100 / 0"})
    assert response.status_code in [400, 422]
    data = response.json()
    assert "detail" in data


def test_calc_code_injection_security_rejection():
    response = client.post("/tools/calc", json={"expression": "__import__('os').system('id')"})
    assert response.status_code in [400, 403, 422]


def test_calc_missing_payload():
    response = client.post("/tools/calc", json={})
    assert response.status_code == 422


def test_search_matched_query():
    response = client.post("/tools/search", json={"query": "langgraph", "limit": 5})
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert isinstance(data["results"], list)


def test_search_missing_query():
    response = client.post("/tools/search", json={})
    assert response.status_code == 422


@pytest.mark.parametrize("ssrf_target_url", [
    "http://127.0.0.1",
    "http://localhost",
    "http://169.254.169.254/latest/meta-data/",
    "http://10.0.0.1",
    "http://192.168.1.1",
    "file:///etc/passwd",
    "gopher://127.0.0.1:6379/_FLUSHALL",
])
def test_scrape_ssrf_rejection_security_gate(ssrf_target_url):
    response = client.post("/tools/scrape", json={"url": ssrf_target_url})
    assert response.status_code in [400, 403, 422]


def test_scrape_missing_url():
    response = client.post("/tools/scrape", json={})
    assert response.status_code == 422


def test_get_catalog_all():
    response = client.get("/catalog")
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    assert len(items) == 50


def test_get_catalog_query_filter():
    response = client.get("/catalog?query=telegram")
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    assert len(items) > 0


def test_get_catalog_categories():
    response = client.get("/catalog/categories")
    assert response.status_code == 200
    data = response.json()
    assert "categories" in data
    assert len(data["categories"]) > 0
