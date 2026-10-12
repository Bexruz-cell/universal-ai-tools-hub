---
name: search-catalog
description: >-
  Search the curated 2026 Top-50 GitHub AI repositories catalog covering Custom Actions,
  OpenAPI specifications, MCP servers, web scrapers, and autonomous agents.
  Use this skill to discover proven open-source AI tools, examine repository use cases, and select integrations.
---

# Search Catalog Skill

The `search-catalog` skill indexes the 2026 Top-50 GitHub AI Repositories ecosystem catalog, categorized into Custom Actions, Web Scraping, MCP Integrations, Social & Messaging Agents, and Workflow Automation.

## Capabilities

- Query and filter 50 curated GitHub projects with descriptions, GitHub links, stars, and AI agent use cases.
- Fast keyword search matching project names, summaries, and agent capabilities.
- Local high-speed execution requiring zero external network calls.

## Interfaces

1. **Model Context Protocol (MCP)**: `search_catalog` tool via stdio bridge.
2. **REST API**: `GET /catalog` and `GET /catalog/categories`.
3. **Direct Python SDK**: `from src.core.tools import search_catalog, search_catalog_2026`.

## Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | string | No | `""` | Search keyword (e.g. `firecrawl`, `mcp`, `telegram`). |
| `limit` | integer | No | `20` | Maximum items to return (1–50). |

## Usage Examples

### 1. MCP stdio Call
```json
{
  "name": "search_catalog",
  "arguments": {
    "query": "scraping",
    "limit": 5
  }
}
```

### 2. REST API Request
```http
GET /catalog?query=browser&limit=5 HTTP/1.1
Host: localhost:8000
```
