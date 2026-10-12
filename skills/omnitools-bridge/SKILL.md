---
name: omnitools-bridge
description: Universal tool bridge providing web scraping, YouTube transcripts, crypto & forex tickers, and the 2026 AI tool catalog for Antigravity, Claude, and ChatGPT.
---

# OmniTools Universal AI Bridge Skill

This skill provides multi-model capabilities across Google Antigravity, Anthropic Claude, and OpenAI ChatGPT / Codex.

## Capabilities

1. **Web Scraper & Reader (`scrape_web` / `/api/v1/web/scrape`)**:
   - Converts any webpage into clean, readable Markdown/text.
   - Strips ads, scripts, navbars, and boilerplate.

2. **YouTube Video Transcriber (`get_youtube_transcript` / `/api/v1/youtube/transcript`)**:
   - Extracts complete video transcripts and subtitles across multiple languages (ru, en).
   - Enables instant summarization of videos and podcasts.

3. **Crypto Market Tickers (`get_crypto_prices` / `/api/v1/crypto/price`)**:
   - Real-time prices, 24h change %, and market stats for BTC, ETH, SOL, TON, TRX.

4. **Fiat Currency Converter (`convert_currency` / `/api/v1/finance/convert`)**:
   - Live conversion rates between USD, EUR, RUB, CNY, KZT.

5. **2026 Top-50 AI Catalog (`search_catalog` / `/api/v1/catalog`)**:
   - Programmatic search across the 50 best open-source AI projects (MCP, Agents, Scraping, Actions).

## How to use in Antigravity:
Execute tools via the built-in MCP server (`src/adapters/mcp_adapter.py`) or import functions from `src.core.tools`.
