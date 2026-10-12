---
name: scrape-web
description: >-
  Fetch, extract, and clean content from web pages into LLM-optimized Markdown and text,
  stripping ads, boilerplate, navigation, and scripts with hardened SSRF protection.
  Use this skill when analyzing articles, documentation, blog posts, GitHub readmes,
  or any specific URL provided by the user.
---

# Web Scraper Skill

The `scrape-web` skill converts raw HTML web pages into stripped, clean, readable text and Markdown with comprehensive Server-Side Request Forgery (SSRF) defense. It eliminates scripts, stylesheets, navigation bars, headers, footers, and tracking elements, preserving token capacity for LLM reasoning.

## Security & SSRF Protection

All outbound HTTP requests are strictly protected:
- **Private & Loopback IP Blocking**: Direct rejection of `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, and IPv6 equivalents (`::1`, `fe80::/10`, `fc00::/7`).
- **Cloud Metadata Defense**: Rejection of `169.254.169.254` (AWS, GCP, Azure metadata).
- **DNS Resolution Validation**: Resolves and verifies every IP address before connection.
- **Redirect Security**: Validates every redirect step to prevent redirect-based SSRF and DNS rebinding.

## Architecture & Interfaces

1. **MCP Tool**: `scrape_web(url, max_length)` via stdio bridge.
2. **REST API**: `POST /tools/scrape` and `GET /api/v1/web/scrape?url={url}&max_length={max_length}`.
3. **Python SDK**: `from src.core.tools import scrape_web`.

## Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `url` | string | **Yes** | — | Fully qualified target URL (`http://` or `https://`). |
| `max_length` | integer | No | `8000` | Maximum character length of the returned content (100–32000). |

## Usage Examples

### 1. Antigravity / Claude / Codex MCP Tool Call
```json
{
  "name": "scrape_web",
  "arguments": {
    "url": "https://docs.python.org/3/whatsnew/3.13.html",
    "max_length": 8000
  }
}
```

### 2. HTTP / REST API (ChatGPT Custom Action)
```http
POST /tools/scrape HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "url": "https://news.ycombinator.com",
  "max_length": 4000
}
```
