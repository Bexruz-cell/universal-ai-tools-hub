from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict, Any
from pathlib import Path
import sys

# Add project root
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.core.tools import (
    search_catalog_2026,
    scrape_web_page,
    get_youtube_transcript,
    get_crypto_prices,
    convert_fiat
)

app = FastAPI(
    title="OmniTools Universal AI Hub API",
    description="Triple-compatible Tool Hub for Antigravity, Claude, and ChatGPT/Codex. Provides web scraping, YouTube transcripts, crypto & forex data, and 2026 Top-50 AI Catalog.",
    version="1.0.0",
    servers=[
        {"url": "http://localhost:8000", "description": "Local server (for ngrok/cloudflare tunnel)"}
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://chat.openai.com", "https://chatgpt.com", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
def get_ai_plugin_manifest():
    manifest_path = Path(__file__).resolve().parent.parent.parent / ".well-known" / "ai-plugin.json"
    if manifest_path.exists():
        return FileResponse(manifest_path, media_type="application/json")
    return {
        "schema_version": "v1",
        "name_for_human": "OmniTools SuperHub",
        "name_for_model": "omnitools_superhub",
        "description_for_human": "Universal tools for web reading, YouTube analysis, crypto tickers, and currency conversion.",
        "description_for_model": "Access real-time web scraping, YouTube transcripts, crypto prices, and currency conversion.",
        "auth": {"type": "none"},
        "api": {"type": "openapi", "url": "http://localhost:8000/openapi.json"}
    }

@app.get("/", summary="Root Status")
def root():
    return {
        "status": "online",
        "service": "OmniTools Universal AI Hub",
        "supported_ecosystems": ["Antigravity", "Claude (MCP)", "ChatGPT / Codex (OpenAPI)"],
        "docs": "/docs",
        "openapi": "/openapi.json"
    }

@app.get("/api/v1/catalog", summary="Search 2026 AI Tools Catalog")
def api_catalog(
    query: Optional[str] = Query(None, description="Search keyword in repos"),
    limit: int = Query(50, ge=1, le=50)
):
    return search_catalog_2026(query=query, limit=limit)

@app.get("/api/v1/web/scrape", summary="Extract clean text from URL")
async def api_scrape(
    url: str = Query(..., description="Target webpage URL"),
    max_length: int = Query(8000, description="Max character length")
):
    res = await scrape_web_page(url=url, max_length=max_length)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@app.get("/api/v1/youtube/transcript", summary="Extract YouTube Subtitles")
def api_youtube(
    video: str = Query(..., description="YouTube URL or Video ID"),
    languages: Optional[str] = Query("ru,en", description="Languages comma-separated")
):
    res = get_youtube_transcript(video=video, languages=languages or "ru,en")
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res

@app.get("/api/v1/crypto/price", summary="Live Crypto Prices")
async def api_crypto(
    coins: str = Query("btc,eth,sol,ton", description="Tickers comma-separated")
):
    res = await get_crypto_prices(coins=coins)
    if "error" in res and not res.get("data"):
        raise HTTPException(status_code=500, detail=res["error"])
    return res

@app.get("/api/v1/finance/convert", summary="Currency Converter")
async def api_convert(
    amount: float = Query(1.0, ge=0.01),
    from_curr: str = Query("USD"),
    to_curr: str = Query("RUB")
):
    res = await convert_fiat(amount=amount, from_curr=from_curr, to_curr=to_curr)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res
