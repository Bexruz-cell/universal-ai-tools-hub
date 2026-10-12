import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from server.main import app

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "version" in data

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_catalog_all():
    response = client.get("/api/v1/catalog")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 50
    assert items[0]["name"] != ""
    assert "github_url" in items[0]

def test_catalog_search():
    response = client.get("/api/v1/catalog?query=youtube")
    assert response.status_code == 200
    items = response.json()
    assert len(items) > 0
    assert any("youtube" in i["name"].lower() or "youtube" in i["description"].lower() for i in items)

def test_finance_convert_same_currency():
    response = client.get("/api/v1/finance/convert?amount=100&from_curr=USD&to_curr=USD")
    assert response.status_code == 200
    data = response.json()
    assert data["converted_amount"] == 100.0
    assert data["rate"] == 1.0

def test_crypto_price_structure():
    # Test endpoint responds with valid schema
    response = client.get("/api/v1/crypto/price?coins=btc")
    # Even if external API has network issues, check that status is handled gracefully
    assert response.status_code in [200, 500]
    if response.status_code == 200:
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 1
        assert data["data"][0]["symbol"] == "BTC"
