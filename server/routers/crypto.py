from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, List
import httpx

router = APIRouter(prefix="/crypto", tags=["Crypto & Markets"])

class CryptoPriceItem(BaseModel):
    symbol: str
    name: str
    price_usd: float
    change_24h_percent: float
    market_cap_usd: float

class CryptoPricesResponse(BaseModel):
    data: List[CryptoPriceItem]
    source: str

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

@router.get("/price", response_model=CryptoPricesResponse, summary="Get live cryptocurrency prices and market data")
async def get_crypto_price(
    coins: str = Query("btc,eth,sol,ton", description="Comma-separated ticker symbols (e.g. btc,eth,sol,ton)")
):
    """
    Fetches real-time price, 24h percentage change, and market cap for requested cryptocurrencies.
    No API keys required.
    """
    coin_list = [c.strip().lower() for c in coins.split(",") if c.strip()]
    ids = [COINGECKO_MAP.get(c, c) for c in coin_list]
    ids_param = ",".join(ids)

    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids_param}&vs_currencies=usd&include_24hr_change=true&include_market_cap=true"
    
    headers = {"Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                raw_data = resp.json()
                results = []
                for sym in coin_list:
                    cid = COINGECKO_MAP.get(sym, sym)
                    item = raw_data.get(cid, {})
                    results.append(CryptoPriceItem(
                        symbol=sym.upper(),
                        name=cid.replace("-", " ").title(),
                        price_usd=float(item.get("usd", 0.0)),
                        change_24h_percent=round(float(item.get("usd_24h_change", 0.0)), 2),
                        market_cap_usd=float(item.get("usd_market_cap", 0.0))
                    ))
                return CryptoPricesResponse(data=results, source="CoinGecko Public API")
    except Exception:
        pass

    # Fallback to Binance public ticker API if CoinGecko rate-limited
    fallback_results = []
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            for sym in coin_list:
                ticker = f"{sym.upper()}USDT"
                b_resp = await client.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={ticker}")
                if b_resp.status_code == 200:
                    d = b_resp.json()
                    fallback_results.append(CryptoPriceItem(
                        symbol=sym.upper(),
                        name=sym.upper(),
                        price_usd=float(d.get("lastPrice", 0.0)),
                        change_24h_percent=round(float(d.get("priceChangePercent", 0.0)), 2),
                        market_cap_usd=0.0
                    ))
        if fallback_results:
            return CryptoPricesResponse(data=fallback_results, source="Binance Public Ticker")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch market data: {str(e)}")

    raise HTTPException(status_code=500, detail="Crypto price sources unavailable at the moment")
