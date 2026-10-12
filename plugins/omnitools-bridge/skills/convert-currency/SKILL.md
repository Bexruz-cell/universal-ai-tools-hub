---
name: convert-currency
description: >-
  Convert between world fiat currencies (USD, EUR, RUB, CNY, KZT, GBP, JPY) in real-time.
  Use this skill whenever currency values need to be exchanged, financial amounts converted,
  or foreign exchange rates queried.
---

# Convert Currency Skill

The `convert-currency` skill provides fast, accurate fiat currency conversion for AI agents across OpenAI Codex, Google Antigravity, Anthropic Claude, and ChatGPT Actions.

## Capabilities

- Real-time exchange rate calculation across major world currencies (USD, EUR, RUB, CNY, KZT, GBP, JPY, CAD, CHF, AUD).
- Primary live exchange rates feed with fallback to cached central bank rates.
- Full compatibility with OpenAPI REST schemas, MCP stdio protocol, and direct Python SDK.

## Interfaces

1. **Model Context Protocol (MCP)**: `convert_currency` tool via stdio bridge.
2. **REST API**: `POST /tools/convert` and legacy `GET /api/v1/finance/convert`.
3. **Direct Python SDK**: `from src.core.tools import convert_currency, convert_fiat`.

## Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `amount` | number | **Yes** | — | Amount to convert. |
| `from_curr` | string | **Yes** | — | Source currency ISO code (e.g. `USD`, `EUR`, `RUB`). |
| `to_curr` | string | **Yes** | — | Target currency ISO code (e.g. `USD`, `EUR`, `RUB`). |

## Usage Examples

### 1. MCP stdio Call
```json
{
  "name": "convert_currency",
  "arguments": {
    "amount": 100,
    "from_curr": "USD",
    "to_curr": "EUR"
  }
}
```

### 2. REST API Request
```http
POST /tools/convert HTTP/1.1
Content-Type: application/json

{
  "amount": 1500,
  "from_curr": "USD",
  "to_curr": "RUB"
}
```
