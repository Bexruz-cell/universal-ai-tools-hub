"""Security Test Suite: SSRF Protection Gate

Validates that all forms of private, loopback, link-local, cloud metadata,
and non-HTTP schemes are strictly blocked by the SSRF defense engine.
"""

import pytest
from src.core.tools import validate_url_ssrf, SSRFSecurityError, scrape_web


@pytest.mark.parametrize("blocked_url", [
    # IPv4 Loopback
    "http://127.0.0.1",
    "http://127.0.0.1:8080/admin",
    "http://127.1.2.3",
    "http://localhost",
    "http://localhost:3000",
    "http://0.0.0.0",
    # Cloud Metadata Services
    "http://169.254.169.254/latest/meta-data/",
    "http://169.254.169.254",
    # RFC 1918 Private Class A
    "http://10.0.0.1",
    "http://10.255.255.254/internal",
    # RFC 1918 Private Class B
    "http://172.16.0.1",
    "http://172.31.255.255:8000",
    # RFC 1918 Private Class C
    "http://192.168.1.1",
    "http://192.168.0.254",
    # IPv6 Loopback & Link-Local
    "http://[::1]",
    "http://[::1]:8080",
    "http://[fe80::1]",
    # Non-HTTP Schemes
    "file:///etc/passwd",
    "file:///C:/Windows/System32/drivers/etc/hosts",
    "gopher://127.0.0.1:6379/_FLUSHALL",
    "ftp://internal.vault/secrets",
    "dict://127.0.0.1:11211",
])
def test_ssrf_validator_blocks_dangerous_urls(blocked_url):
    """Ensure validate_url_ssrf raises SSRFSecurityError on dangerous targets."""
    with pytest.raises(SSRFSecurityError):
        validate_url_ssrf(blocked_url)


@pytest.mark.asyncio
@pytest.mark.parametrize("blocked_url", [
    "http://127.0.0.1:9999",
    "http://169.254.169.254/meta-data",
    "http://10.0.0.1",
    "file:///etc/passwd",
])
async def test_scrape_web_returns_blocked_error(blocked_url):
    """Ensure scrape_web safely traps SSRF and returns blocked response dictionary."""
    res = await scrape_web(blocked_url)
    assert "error" in res
    assert "blocked" in res.get("status", "") or "SSRF blocked" in res["error"]


def test_ssrf_validator_allows_valid_public_domain():
    """Ensure validate_url_ssrf permits legitimate public HTTP/HTTPS URLs."""
    parsed = validate_url_ssrf("https://example.com")
    assert parsed.scheme == "https"
    assert parsed.hostname == "example.com"
