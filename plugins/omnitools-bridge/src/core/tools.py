"""OmniTools Universal AI Bridge - Core Tools Engine

Production-grade implementations of the 5 core tools with hardened SSRF defense,
AST-sandboxed math evaluator, YouTube transcript extraction, dual-engine crypto ticker,
and 2026 AI catalog search.
"""

import ast
import asyncio
import ipaddress
import json
import math
import operator
import re
import socket
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List, Optional

import httpx
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi

# ==============================================================================
# 1. HARDENED SSRF DEFENSE ENGINE
# ==============================================================================

BLOCKED_NETWORKS = [
    # IPv4 Private, Loopback, Link-Local, and Reserved
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),       # CGNAT
    ipaddress.ip_network("127.0.0.0/8"),        # Loopback
    ipaddress.ip_network("169.254.0.0/16"),     # Link-Local & AWS/GCP/Azure Metadata
    ipaddress.ip_network("172.16.0.0/12"),      # Private RFC 1918
    ipaddress.ip_network("192.0.0.0/24"),       # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),       # TEST-NET-1
    ipaddress.ip_network("192.168.0.0/16"),     # Private RFC 1918
    ipaddress.ip_network("198.18.0.0/15"),      # Benchmark testing
    ipaddress.ip_network("198.51.100.0/24"),    # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),     # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),        # Multicast
    ipaddress.ip_network("240.0.0.0/4"),        # Reserved for future use
    ipaddress.ip_network("255.255.255.255/32"), # Broadcast
    # IPv6 Loopback, Link-Local, ULA, and Reserved
    ipaddress.ip_network("::1/128"),            # Loopback
    ipaddress.ip_network("::/128"),             # Unspecified
    ipaddress.ip_network("::ffff:0:0/96"),      # IPv4-mapped IPv6 prefix
    ipaddress.ip_network("64:ff9b::/96"),       # IPv4-IPv6 translation
    ipaddress.ip_network("100::/64"),           # Discard prefix
    ipaddress.ip_network("2001:db8::/32"),      # Documentation
    ipaddress.ip_network("fc00::/7"),           # Unique Local Address (ULA)
    ipaddress.ip_network("fe80::/10"),          # Link-Local
    ipaddress.ip_network("ff00::/8"),           # Multicast
]


class SSRFSecurityError(ValueError):
    """Raised when a target URL violates SSRF security boundaries."""
    pass


def is_ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address belongs to any blocked CIDR network."""
    # Unpack IPv4-mapped IPv6 address (e.g., ::ffff:127.0.0.1)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped

    for net in BLOCKED_NETWORKS:
        try:
            if ip in net:
                return True
        except TypeError:
            continue
    return False


def validate_url_ssrf(url: str) -> urllib.parse.ParseResult:
    """Validate a URL against SSRF threats including scheme, credentials, and DNS resolution.

    Raises:
        SSRFSecurityError: If the URL or any resolved IP address is disallowed.
    """
    if not url or not isinstance(url, str):
        raise SSRFSecurityError("URL must be a non-empty string.")

    url_clean = url.strip()
    parsed = urllib.parse.urlsplit(url_clean)

    # 1. Scheme validation (strictly http and https)
    if parsed.scheme.lower() not in ("http", "https"):
        raise SSRFSecurityError(f"Disallowed scheme: '{parsed.scheme}'. Only http and https are permitted.")

    # 2. Hostname extraction
    hostname = parsed.hostname
    if not hostname:
        raise SSRFSecurityError("URL must contain a valid host name.")

    # 3. Disallow user credentials embedded in URL
    if parsed.username or parsed.password:
        raise SSRFSecurityError("User credentials in URL are prohibited.")

    # 4. Check if host is direct IP literal
    try:
        # Handle bracketed IPv6 literals
        host_ip_str = hostname.strip("[]")
        ip_obj = ipaddress.ip_address(host_ip_str)
        if is_ip_blocked(ip_obj):
            raise SSRFSecurityError(f"Direct IP access to restricted address is blocked: {ip_obj}")
        return parsed
    except ValueError:
        # Not an IP literal, proceed to DNS resolution
        pass

    # 5. DNS Resolution Pre-check
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    try:
        addr_info = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise SSRFSecurityError(f"DNS resolution failed for host '{hostname}': {e}")

    if not addr_info:
        raise SSRFSecurityError(f"No IP addresses resolved for host '{hostname}'.")

    # 6. Verify every resolved address
    for family, socktype, proto, canonname, sockaddr in addr_info:
        ip_str = sockaddr[0]
        try:
            resolved_ip = ipaddress.ip_address(ip_str)
            if is_ip_blocked(resolved_ip):
                raise SSRFSecurityError(
                    f"Host '{hostname}' resolved to blocked IP: {resolved_ip}"
                )
        except ValueError:
            raise SSRFSecurityError(f"Invalid resolved IP format: {ip_str}")

    return parsed


# ==============================================================================
# 2. CORE TOOL: SCRAPE WEB WITH SSRF PROTECTION
# ==============================================================================

async def scrape_web(
    url: str,
    max_length: int = 8000,
    extract_main_text: bool = True
) -> Dict[str, Any]:
    """Fetch, sanitize, and extract readable text from a URL with full SSRF protection."""
    # 1. SSRF validation of initial target URL
    try:
        validate_url_ssrf(url)
    except SSRFSecurityError as err:
        return {"error": f"SSRF blocked: {err}", "url": url, "status": "blocked"}

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
    }

    current_url = url
    max_redirects = 5
    redirect_count = 0

    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=False,
            verify=True
        ) as client:
            while True:
                resp = await client.get(current_url, headers=headers)

                # Check for redirects manually to validate each destination URL against SSRF
                if resp.status_code in (301, 302, 303, 307, 308):
                    redirect_count += 1
                    if redirect_count > max_redirects:
                        return {"error": "Too many redirects", "url": current_url}

                    location = resp.headers.get("Location")
                    if not location:
                        return {"error": "Redirect missing Location header", "url": current_url}

                    # Resolve relative redirect URLs
                    next_url = urllib.parse.urljoin(current_url, location)

                    # Hardened SSRF check on redirect destination
                    try:
                        validate_url_ssrf(next_url)
                    except SSRFSecurityError as sec_err:
                        return {
                            "error": f"SSRF blocked on redirect to {next_url}: {sec_err}",
                            "url": next_url,
                            "status": "blocked"
                        }

                    current_url = next_url
                    continue

                if resp.status_code >= 400:
                    return {"error": f"HTTP {resp.status_code}", "url": current_url}

                html_text = resp.text
                break
    except httpx.TimeoutException:
        return {"error": "Request timed out after 10.0 seconds", "url": current_url}
    except Exception as exc:
        return {"error": f"Network error: {str(exc)}", "url": current_url}

    # Clean HTML content
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "aside", "iframe"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else "No Title"
    desc_meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    desc = desc_meta.get("content", "").strip() if desc_meta else ""

    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    clean_text = "\n".join(lines)[:max_length]

    return {
        "url": current_url,
        "title": title,
        "description": desc,
        "text": clean_text,
        "length": len(clean_text)
    }


# Backwards compatibility alias
scrape_web_page = scrape_web


# ==============================================================================
# 3. CORE TOOL: AST-SANDBOXED MATHEMATICAL CALCULATOR
# ==============================================================================

ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

ALLOWED_FUNCTIONS = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "exp": math.exp,
    "abs": abs,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
    "min": min,
    "max": max,
    "pow": math.pow,
}

ALLOWED_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}


def _eval_node(node: ast.AST) -> float:
    """Recursively evaluate an AST node within strict whitelist bounds."""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"Disallowed constant type: {type(node.value).__name__}")

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in ALLOWED_OPERATORS:
            raise ValueError(f"Disallowed binary operator: {op_type.__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if op_type in (ast.Div, ast.FloorDiv, ast.Mod) and right == 0:
            raise ZeroDivisionError("Division by zero is undefined")
        if op_type == ast.Pow and (left > 1000 or right > 100):
            raise OverflowError("Exponentiation exceeds safe computation threshold")
        return ALLOWED_OPERATORS[op_type](left, right)

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in ALLOWED_OPERATORS:
            raise ValueError(f"Disallowed unary operator: {op_type.__name__}")
        operand = _eval_node(node.operand)
        return ALLOWED_OPERATORS[op_type](operand)

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only direct named mathematical functions are allowed")
        func_name = node.func.id
        if func_name not in ALLOWED_FUNCTIONS:
            raise ValueError(f"Disallowed function: '{func_name}'")
        args = [_eval_node(arg) for arg in node.args]
        return float(ALLOWED_FUNCTIONS[func_name](*args))

    if isinstance(node, ast.Name):
        if node.id in ALLOWED_CONSTANTS:
            return float(ALLOWED_CONSTANTS[node.id])
        raise ValueError(f"Undefined identifier or variable: '{node.id}'")

    raise ValueError(f"Disallowed syntax node: {type(node).__name__}")


def calc_expression(expression: str, precision: int = 4) -> Dict[str, Any]:
    """Safely parse and evaluate a mathematical expression using an AST sandbox."""
    if not expression or not expression.strip():
        return {"error": "Expression cannot be empty", "expression": expression}

    cleaned = expression.strip()
    try:
        tree = ast.parse(cleaned, mode="eval")
        raw_val = _eval_node(tree)
        rounded = round(raw_val, precision) if precision > 0 else round(raw_val)
        return {
            "expression": cleaned,
            "result": rounded,
            "raw_result": raw_val,
            "formatted": f"{rounded:,}"
        }
    except ZeroDivisionError:
        return {"error": "Division by zero is undefined", "expression": cleaned}
    except OverflowError as oe:
        return {"error": f"Numeric overflow: {oe}", "expression": cleaned}
    except (SyntaxError, ValueError) as err:
        return {"error": f"Invalid expression: {err}", "expression": cleaned}
    except Exception as exc:
        return {"error": f"Computation error: {str(exc)}", "expression": cleaned}


# ==============================================================================
# 4. CORE TOOL: DEEP SEARCH
# ==============================================================================

async def deep_search(
    query: str,
    num_results: int = 5,
    depth: int = 1
) -> Dict[str, Any]:
    """Execute a comprehensive web search query with structured result formatting."""
    if not query or not query.strip():
        return {"error": "Query cannot be empty", "results": []}

    q = query.strip()
    results = []

    # Attempt query execution via DuckDuckGo HTML endpoint
    search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(q)}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.post(search_url, data={"q": q}, headers=headers)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for item in soup.find_all("div", class_="result"):
                    title_elem = item.find("a", class_="result__a")
                    snippet_elem = item.find("a", class_="result__snippet")
                    if title_elem:
                        href = title_elem.get("href", "")
                        # Unwrap DDG redirect url
                        if "uddg=" in href:
                            m = re.search(r"uddg=([^&]+)", href)
                            if m:
                                href = urllib.parse.unquote(m.group(1))
                        results.append({
                            "title": title_elem.get_text(strip=True),
                            "url": href,
                            "snippet": snippet_elem.get_text(strip=True) if snippet_elem else ""
                        })
                    if len(results) >= num_results:
                        break
    except Exception:
        pass

    # If live search is rate-limited or unavailable, search against curated catalog knowledge
    if not results:
        catalog_items = search_catalog_2026(query=q, limit=num_results)
        for cat in catalog_items:
            results.append({
                "title": cat.get("name", "Catalog Entry"),
                "url": cat.get("github_url", "https://github.com"),
                "snippet": f"{cat.get('description', '')} - Use Case: {cat.get('use_case', '')}"
            })

    return {
        "query": q,
        "depth": depth,
        "total_results": len(results),
        "results": results[:num_results]
    }


# ==============================================================================
# 5. CORE TOOL: YOUTUBE TRANSCRIPT EXTRACTION
# ==============================================================================

def youtube_transcript(video: str, languages: str = "ru,en") -> Dict[str, Any]:
    """Extract full subtitles/transcript text from a YouTube video URL or ID."""
    url_or_id = video.strip()
    video_id = url_or_id
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11})(?:[?&]|$)',
        r'youtu\.be\/([0-9A-Za-z_-]{11})',
        r'shorts\/([0-9A-Za-z_-]{11})'
    ]
    for p in patterns:
        m = re.search(p, url_or_id)
        if m:
            video_id = m.group(1)
            break

    lang_list = [l.strip() for l in languages.split(",") if l.strip()]
    try:
        data = YouTubeTranscriptApi.get_transcript(video_id, languages=lang_list)
    except Exception:
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = (
                transcript_list.find_transcript(lang_list)
                or transcript_list.find_generated_transcript(lang_list)
                or transcript_list.find_transcript(['en', 'ru'])
                or transcript_list.find_generated_transcript(['en', 'ru'])
            )
            data = transcript.fetch()
        except Exception as e:
            return {"error": f"Subtitles not found for {video_id}: {str(e)}", "video_id": video_id}

    full_text = " ".join([i["text"] for i in data])
    return {
        "video_id": video_id,
        "full_text": full_text,
        "total_segments": len(data),
        "sample_segments": data[:50]
    }


# Backwards compatibility alias
get_youtube_transcript = youtube_transcript


# ==============================================================================
# 6. CORE TOOL: CRYPTO PRICES WITH DUAL FALLBACK
# ==============================================================================

COINGECKO_MAP = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "sol": "solana",
    "ton": "the-open-network",
    "trx": "tron",
    "bnb": "binancecoin",
    "doge": "dogecoin",
    "xrp": "ripple",
    "usdt": "tether"
}


async def crypto_price(
    coins: str = "btc,eth,sol,ton",
    vs_currency: str = "usd"
) -> Dict[str, Any]:
    """Fetch live cryptocurrency spot prices with CoinGecko -> Binance fallback."""
    coin_list = [c.strip().lower() for c in coins.split(",") if c.strip()]
    ids = [COINGECKO_MAP.get(c, c) for c in coin_list]
    ids_param = ",".join(ids)
    vs_curr = vs_currency.lower()

    # 1. Primary engine: CoinGecko API
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids_param}&vs_currencies={vs_curr}&include_24hr_change=true"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, headers={"Accept": "application/json"})
            if resp.status_code == 200:
                raw = resp.json()
                results = []
                for sym in coin_list:
                    cid = COINGECKO_MAP.get(sym, sym)
                    item = raw.get(cid, {})
                    results.append({
                        "symbol": sym.upper(),
                        "price_usd": float(item.get(vs_curr, 0.0)),
                        "change_24h": round(float(item.get(f"{vs_curr}_24h_change", 0.0)), 2)
                    })
                return {"data": results, "source": "CoinGecko", "currency": vs_curr.upper()}
    except Exception:
        pass

    # 2. Resilient fallback engine: Binance Ticker API
    fallback = []
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            for sym in coin_list:
                ticker = f"{sym.upper()}USDT"
                resp = await client.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={ticker}")
                if resp.status_code == 200:
                    d = resp.json()
                    fallback.append({
                        "symbol": sym.upper(),
                        "price_usd": float(d.get("lastPrice", 0.0)),
                        "change_24h": round(float(d.get("priceChangePercent", 0.0)), 2)
                    })
        return {"data": fallback, "source": "Binance Ticker", "currency": "USD"}
    except Exception as e:
        return {"error": str(e), "data": [], "source": "None"}


# Backwards compatibility alias
get_crypto_prices = crypto_price


# ==============================================================================
# 7. UTILITY: CATALOG 2026 & FOREX CONVERTER
# ==============================================================================

def search_catalog_2026(query: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Search and filter the 2026 Top-50 GitHub repositories catalog."""
    base_dirs = [
        Path(__file__).resolve().parent.parent.parent / "catalog",
        Path(__file__).resolve().parent.parent / "catalog",
        Path.cwd() / "catalog",
    ]
    catalog_path = None
    for d in base_dirs:
        p2026 = d / "catalog_2026.json"
        if p2026.exists():
            catalog_path = p2026
            break
        p = d / "catalog.json"
        if p.exists():
            catalog_path = p
            break

    if not catalog_path or not catalog_path.exists():
        return []

    with open(catalog_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    if query:
        q = query.lower()
        items = [
            i for i in items
            if q in i.get("name", "").lower()
            or q in i.get("description", "").lower()
            or q in i.get("use_case", "").lower()
            or q in i.get("chatgpt_use_case", "").lower()
        ]
    return items[:limit]


RATES_CACHE = {
    "USD": 1.0,
    "EUR": 0.92,
    "RUB": 94.5,
    "CNY": 7.23,
    "KZT": 450.0,
    "GBP": 0.79,
    "JPY": 154.2
}


async def convert_fiat(amount: float, from_curr: str, to_curr: str) -> Dict[str, Any]:
    """Convert between fiat currencies using real-time or cached rates."""
    f = from_curr.upper()
    t = to_curr.upper()
    if f == t:
        return {"amount": amount, "from": f, "to": t, "converted": float(amount), "rate": 1.0}

    # Fetch fresh open exchange rates if available
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get("https://open.er-api.com/v6/latest/USD")
            if resp.status_code == 200:
                rates = resp.json().get("rates", {})
                if f in rates and t in rates:
                    usd_amount = amount / rates[f]
                    result = usd_amount * rates[t]
                    rate = rates[t] / rates[f]
                    return {
                        "amount": amount,
                        "from": f,
                        "to": t,
                        "converted": round(result, 2),
                        "rate": round(rate, 4),
                        "source": "Open Exchange Rates"
                    }
    except Exception:
        pass

    # Reliable fallback cache
    if f in RATES_CACHE and t in RATES_CACHE:
        usd_amount = amount / RATES_CACHE[f]
        result = usd_amount * RATES_CACHE[t]
        rate = RATES_CACHE[t] / RATES_CACHE[f]
        return {
            "amount": amount,
            "from": f,
            "to": t,
            "converted": round(result, 2),
            "rate": round(rate, 4),
            "source": "Cached Central Bank Rates"
        }

    return {"error": f"Unsupported currency conversion: {f} -> {t}"}
