---
name: deep-search
description: >-
  Execute comprehensive, multi-depth web searches and iterative deep research across multiple sources.
  Use this skill when the user requires in-depth research, multi-query topic synthesis, recent news
  investigation, or answers to complex questions that cannot be satisfied by a single search query.
---

# Deep Search Skill

The `deep-search` skill equips AI agents (Antigravity, Claude, ChatGPT/Codex) with multi-iteration web searching capabilities, traversing search engine results and synthesizing findings across disparate domains.

## Architecture & Interfaces

The tool is accessible through three unified interfaces:
1. **Model Context Protocol (MCP)**: `deep_search` tool via stdio bridge.
2. **REST API**: `POST /tools/search` and `GET /api/v1/catalog` via `api_adapter.py`.
3. **Direct Python SDK**: `from src.core.tools import deep_search`.

## Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | string | **Yes** | — | Search query string or research question. |
| `depth` | integer | No | `1` | Research depth: `1` (instant search), `2` (follow-up crawl), `3` (deep cross-reference). Range: 1–3. |
| `num_results` | integer | No | `5` | Maximum number of top results to return (1–20). |

## Execution Runbook

1. **Query Formulation**: Break complex user questions into concise, keyword-rich search queries.
2. **Depth Selection**:
   - `depth=1`: Fast factual lookups and quick reference verification.
   - `depth=2`: Technical architecture, API documentation, and multi-source corroboration.
   - `depth=3`: Exhaustive domain investigation, historical benchmarks, or competitive analysis.
3. **Execution**: Call tool through the appropriate interface.
4. **Synthesis**: Correlate findings, cite source URLs, and present structured findings.

## Usage Examples

### 1. Antigravity / MCP Tool Call
```json
{
  "name": "deep_search",
  "arguments": {
    "query": "Model Context Protocol specifications 2026",
    "depth": 2,
    "num_results": 5
  }
}
```

### 2. HTTP / REST API (ChatGPT Custom Action & Codex)
```http
POST /tools/search HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "query": "Model Context Protocol 2026",
  "depth": 2,
  "limit": 5
}
```
