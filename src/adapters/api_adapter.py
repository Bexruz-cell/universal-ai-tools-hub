"""OmniTools Universal AI Hub - FastAPI & REST Adapter

Exposes OpenAPI 3.1 endpoints for ChatGPT Custom GPT Actions, Codex, and HTTP clients.
Provides both POST /tools/* action endpoints and legacy GET /api/v1/* endpoints.
"""

from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

# Ensure project root in sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.core.tools import (
    calc_expression,
    convert_fiat,
    crypto_price,
    deep_search,
    scrape_web,
    search_catalog_2026,
    youtube_transcript,
)

app = FastAPI(
    title="OmniTools Universal AI Hub API",
    description="Cross-platform Tool Hub compatible with OpenAI Codex, Google Antigravity, Anthropic Claude, and ChatGPT Actions.",
    version="1.0.0",
    servers=[
        {"url": "http://localhost:8000", "description": "Local development server"}
    ]
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://chat.openai.com", "https://chatgpt.com", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------------------
# Pydantic Request Models
# ------------------------------------------------------------------------------

class CalcRequest(BaseModel):
    expression: str = Field(..., description="Mathematical expression to evaluate (e.g. 'sqrt(144) + 10')")
    precision: Optional[int] = Field(4, description="Decimal places for rounding")


class ScrapeRequest(BaseModel):
    url: str = Field(..., description="Target webpage URL to read")
    max_length: Optional[int] = Field(8000, description="Max characters to return")


class YouTubeRequest(BaseModel):
    video: str = Field(..., description="YouTube video URL or 11-char ID")
    languages: Optional[str] = Field("ru,en", description="Comma-separated language priority list")


class CryptoRequest(BaseModel):
    coins: Optional[Union[List[str], str]] = Field("btc,eth,sol,ton", description="Coin symbols or list")
    vs_currency: Optional[str] = Field("usd", description="Target comparison fiat currency")


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search keyword or phrase")
    limit: Optional[int] = Field(5, description="Max results to return")
    depth: Optional[int] = Field(1, description="Depth of research (1-3)")


class ConvertRequest(BaseModel):
    amount: float = Field(1.0, description="Amount to convert", ge=0.01)
    from_curr: str = Field("USD", description="Source currency ISO code")
    to_curr: str = Field("RUB", description="Target currency ISO code")


# ------------------------------------------------------------------------------
# Root and Manifest Endpoints
# ------------------------------------------------------------------------------

@app.get("/", summary="Root Status")
def root():
    return {
        "status": "online",
        "service": "OmniTools Universal AI Hub",
        "version": "1.0.0",
        "supported_ecosystems": ["OpenAI Codex", "Google Antigravity", "Claude (MCP)", "ChatGPT Actions"],
        "docs": "/docs",
        "openapi": "/openapi.json"
    }


@app.get("/health", summary="Health Check")
def health():
    return {"status": "healthy"}


@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
def get_ai_plugin_manifest():
    manifest_path = Path(__file__).resolve().parent.parent.parent / ".well-known" / "ai-plugin.json"
    if manifest_path.exists():
        return FileResponse(manifest_path, media_type="application/json")
    return {
        "schema_version": "v1",
        "name_for_human": "OmniTools SuperHub",
        "name_for_model": "omnitools_superhub",
        "description_for_human": "Universal tools for web reading, YouTube analysis, math calculations, and crypto tickers.",
        "description_for_model": "Access web scraping, YouTube transcripts, math calculator, crypto prices, and currency conversion.",
        "auth": {"type": "none"},
        "api": {"type": "openapi", "url": "http://localhost:8000/openapi.json"}
    }


# ------------------------------------------------------------------------------
# Standardized Tool Actions (POST /tools/*)
# ------------------------------------------------------------------------------

@app.post("/tools/calc", summary="Evaluate Math Expression")
def api_tool_calc(req: CalcRequest):
    res = calc_expression(expression=req.expression, precision=req.precision or 4)
    if "error" in res:
        err_msg = res["error"]
        if "Disallowed" in err_msg or "code injection" in err_msg:
            raise HTTPException(status_code=403, detail=err_msg)
        raise HTTPException(status_code=400, detail=err_msg)
    return res


@app.post("/tools/scrape", summary="Scrape Web Content with SSRF Protection")
async def api_tool_scrape(req: ScrapeRequest):
    res = await scrape_web(url=req.url, max_length=req.max_length or 8000)
    if "error" in res:
        err_str = res["error"]
        if "SSRF blocked" in err_str:
            raise HTTPException(status_code=400, detail=err_str)
        raise HTTPException(status_code=400, detail=err_str)
    return res


@app.post("/tools/youtube", summary="Extract YouTube Subtitles")
def api_tool_youtube(req: YouTubeRequest):
    res = youtube_transcript(video=req.video, languages=req.languages or "ru,en")
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@app.post("/tools/crypto", summary="Query Crypto Spot Prices")
async def api_tool_crypto(req: CryptoRequest):
    coins_arg = req.coins
    if isinstance(coins_arg, list):
        coins_arg = ",".join(coins_arg)
    elif not coins_arg:
        coins_arg = "btc,eth,sol,ton"

    res = await crypto_price(coins=coins_arg, vs_currency=req.vs_currency or "usd")
    if "error" in res and not res.get("data"):
        raise HTTPException(status_code=502, detail=res["error"])
    return res


@app.post("/tools/search", summary="Deep Web & Catalog Search")
async def api_tool_search(req: SearchRequest):
    res = await deep_search(query=req.query, num_results=req.limit or 5, depth=req.depth or 1)
    return res


@app.post("/tools/convert", summary="Convert Fiat Currencies")
async def api_tool_convert(req: ConvertRequest):
    res = await convert_fiat(amount=req.amount, from_curr=req.from_curr, to_curr=req.to_curr)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


# ------------------------------------------------------------------------------
# Catalog Endpoints (GET /catalog)
# ------------------------------------------------------------------------------

@app.get("/catalog", summary="Get 2026 AI Tools Catalog")
def get_catalog(
    query: Optional[str] = Query(None, description="Search keyword in repos"),
    limit: int = Query(50, ge=1, le=50)
):
    return search_catalog_2026(query=query, limit=limit)


@app.get("/catalog/coding", summary="Search Curated 2026 Top-50 Coding Repositories")
def get_coding_catalog(
    query: Optional[str] = Query(None, description="Search keyword in repos"),
    category: Optional[str] = Query(None, description="Category filter (A, B, C, D, E or category name)"),
    limit: int = Query(50, ge=1, le=50)
):
    from src.coding_tools.catalog import search_coding_catalog
    return search_coding_catalog(query=query, category=category, limit=limit)


@app.get("/catalog/categories", summary="Get Catalog Categories")
def get_catalog_categories():
    items = search_catalog_2026(limit=50)
    categories = sorted(list({item.get("category", "General") for item in items if item.get("category")}))
    if not categories:
        categories = ["Actions & OpenAPI", "Scraping & Data", "Integrations & MCP", "Agents & RAG", "Security & QA"]
    return {"categories": categories}



# ------------------------------------------------------------------------------
# Legacy Compatibility Endpoints (GET /api/v1/*)
# ------------------------------------------------------------------------------

@app.get("/api/v1/catalog", summary="Search 2026 AI Tools Catalog (Legacy)")
def api_catalog_legacy(
    query: Optional[str] = Query(None, description="Search keyword in repos"),
    limit: int = Query(50, ge=1, le=50)
):
    return search_catalog_2026(query=query, limit=limit)


@app.get("/api/v1/web/scrape", summary="Extract clean text from URL (Legacy)")
async def api_scrape_legacy(
    url: str = Query(..., description="Target webpage URL"),
    max_length: int = Query(8000, description="Max character length")
):
    res = await scrape_web(url=url, max_length=max_length)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@app.get("/api/v1/youtube/transcript", summary="Extract YouTube Subtitles (Legacy)")
def api_youtube_legacy(
    video: str = Query(..., description="YouTube URL or Video ID"),
    languages: Optional[str] = Query("ru,en", description="Languages comma-separated")
):
    res = youtube_transcript(video=video, languages=languages or "ru,en")
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@app.get("/api/v1/crypto/price", summary="Live Crypto Prices (Legacy)")
async def api_crypto_legacy(
    coins: str = Query("btc,eth,sol,ton", description="Tickers comma-separated")
):
    res = await crypto_price(coins=coins)
    if "error" in res and not res.get("data"):
        raise HTTPException(status_code=500, detail=res["error"])
    return res


@app.get("/api/v1/finance/convert", summary="Currency Converter (Legacy)")
async def api_convert_legacy(
    amount: float = Query(1.0, ge=0.01),
    from_curr: str = Query("USD"),
    to_curr: str = Query("RUB")
):
    res = await convert_fiat(amount=amount, from_curr=from_curr, to_curr=to_curr)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res
