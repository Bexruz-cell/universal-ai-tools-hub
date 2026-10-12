---
name: crypto-price
description: >-
  Query real-time cryptocurrency spot prices, 24-hour percentage changes, and market tickers
  for major crypto assets (BTC, ETH, SOL, TON, TRX, BNB, DOGE, XRP, etc.) with dual-engine fallback
  (CoinGecko & Binance). Use this skill when the user asks for current cryptocurrency prices,
  portfolio valuations, or crypto market performance.
---

# Crypto Price Ticker Skill

The `crypto-price` skill delivers real-time market spot rates and 24-hour price change percentages for cryptocurrencies. Built with high availability in mind, it provides seamless failover between CoinGecko and Binance without requiring paid API keys.

## Architecture & Interfaces

1. **MCP Tool**: `crypto_price(coins, vs_currency)` via stdio bridge.
2. **REST API**: `POST /tools/crypto` and `GET /api/v1/crypto/price?coins={coins}`.
3. **Python SDK**: `from src.core.tools import crypto_price`.

## Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `coins` | string | No | `"btc,eth,sol,ton"` | Comma-separated crypto tickers/symbols (e.g. `"btc,eth,sol,ton,trx,bnb,doge"`). |
| `vs_currency` | string | No | `"usd"` | Target comparison currency (e.g. `"usd"`, `"eur"`, `"rub"`). |

## Usage Examples

### 1. Antigravity / Claude / Codex MCP Tool Call
```json
{
  "name": "crypto_price",
  "arguments": {
    "coins": "btc,eth,sol,ton",
    "vs_currency": "usd"
  }
}
```

### 2. HTTP / REST API (ChatGPT Custom Action)
```http
POST /tools/crypto HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "coins": "btc,eth,sol,ton",
  "vs_currency": "usd"
}
```
