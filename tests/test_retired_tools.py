"""Removed external integrations must not remain callable or advertised."""
import json
from pathlib import Path

from src.core import tools
from src.adapters.api_adapter import app
from src.adapters.mcp_adapter import TOOLS, SYNC_CODING_TOOLS
from server.main import app as legacy_app


def test_retired_tools_absent_and_survivors_preserved():
    names = {tool['name'] for tool in TOOLS}
    assert len(SYNC_CODING_TOOLS) == 15
    assert SYNC_CODING_TOOLS <= names
    assert {'scrape_web', 'calc_expression', 'convert_currency', 'search_catalog', 'deep_search'} <= names
    for name in ('youtube_transcript', 'get_youtube_transcript', 'crypto_price', 'get_crypto_prices', 'COINGECKO_MAP'):
        assert name not in names
        assert not hasattr(tools, name)


def test_retired_http_routes_and_schemas_absent():
    retired = {'/tools/youtube', '/tools/crypto', '/api/v1/youtube/transcript', '/api/v1/crypto/price'}
    root = Path(__file__).resolve().parents[1]
    for schema in (app.openapi(), legacy_app.openapi(),
                   json.loads((root / 'openapi.json').read_text(encoding='utf-8')),
                   json.loads((root / 'server/openapi.json').read_text(encoding='utf-8'))):
        assert retired.isdisjoint(schema['paths'])
        assert {'YouTubeRequest', 'CryptoRequest'}.isdisjoint(schema.get('components', {}).get('schemas', {}))
    assert {'/tools/scrape', '/tools/calc', '/tools/convert', '/catalog'} <= app.openapi()['paths'].keys()
