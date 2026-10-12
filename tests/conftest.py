"""Pytest configuration ensuring project root is in sys.path and providing async test fixtures."""

import sys
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport
from src.adapters.api_adapter import app

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))


@pytest.fixture
async def async_client():
    """Async HTTP test client for OmniTools API testing."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
