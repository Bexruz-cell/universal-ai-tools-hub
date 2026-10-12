import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi

def search_catalog_2026(query: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Search and filter the 2026 Top-50 GitHub repositories catalog."""
    catalog_path = Path(__file__).resolve().parent.parent.parent / "catalog" / "catalog_2026.json"
    if not catalog_path.exists():
        # Fallback to catalog.json
        catalog_path = Path(__file__).resolve().parent.parent.parent / "catalog" / "catalog.json"
    if not catalog_path.exists():
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

async def scrape_web_page(url: str, max_length: int = 8000) -> Dict[str, Any]:
    """Fetch and strip web page HTML to clean text for LLMs."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code >= 400:
            return {"error": f"HTTP {resp.status_code}", "url": url}
        html_text = resp.text

    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "aside"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else "No Title"
    desc_meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    desc = desc_meta.get("content", "").strip() if desc_meta else ""

    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    clean_text = "\n".join(lines)[:max_length]

    return {
        "url": url,
        "title": title,
        "description": desc,
        "text": clean_text,
        "length": len(clean_text)
    }

def get_youtube_transcript(video: str, languages: str = "ru,en") -> Dict[str, Any]:
    """Extract full subtitles/transcript from a YouTube video URL or ID."""
    url_or_id = video.strip()
    video_id = url_or_id
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
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
            transcript = transcript_list.find_transcript(['ru', 'en']) or transcript_list.find_generated_transcript(['ru', 'en'])
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

async def get_crypto_prices(coins: str = "btc,eth,sol,ton") -> Dict[str, Any]:
    """Fetch live crypto prices and 24h change."""
    coin_list = [c.strip().lower() for c in coins.split(",") if c.strip()]
    ids = [COINGECKO_MAP.get(c, c) for c in coin_list]
    ids_param = ",".join(ids)

    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids_param}&vs_currencies=usd&include_24hr_change=true"
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
                        "price_usd": float(item.get("usd", 0.0)),
                        "change_24h": round(float(item.get("usd_24h_change", 0.0)), 2)
                    })
                return {"data": results, "source": "CoinGecko"}
    except Exception:
        pass

    # Fallback Binance
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
        return {"data": fallback, "source": "Binance Ticker"}
    except Exception as e:
        return {"error": str(e), "data": []}

async def convert_fiat(amount: float, from_curr: str, to_curr: str) -> Dict[str, Any]:
    """Convert between currencies."""
    f = from_curr.upper()
    t = to_curr.upper()
    if f == t:
        return {"amount": amount, "from": f, "to": t, "converted": amount, "rate": 1.0}
    
    url = f"https://open.er-api.com/v6/latest/{f}"
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                rates = resp.json().get("rates", {})
                rate = rates.get(t)
                if rate:
                    return {
                        "amount": amount,
                        "from": f,
                        "to": t,
                        "converted": round(amount * rate, 2),
                        "rate": rate
                    }
    except Exception as e:
        return {"error": str(e)}
    return {"error": f"Currency {t} not found"}
