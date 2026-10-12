"""OmniTools Universal AI Bridge - Model Context Protocol (MCP) Stdio Server

Fully compliant with MCP Specification (2024-11-05).
Cross-platform stdio JSON-RPC 2.0 communication supporting Windows, Linux, and macOS.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

# Ensure UTF-8 streams across all operating systems
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

# Dynamically add project root and src directory
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(current_dir.parent) not in sys.path:
    sys.path.insert(0, str(current_dir.parent))

from src.core.tools import (
    deep_search,
    scrape_web,
    youtube_transcript,
    calc_expression,
    crypto_price,
    search_catalog_2026,
    convert_fiat,
)

TOOLS = [
    {
        "name": "deep_search",
        "description": "Execute comprehensive multi-depth web search and recursive exploration.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query or topic"},
                "num_results": {"type": "integer", "description": "Max results to return", "default": 5},
                "depth": {"type": "integer", "description": "Research depth (1-3)", "default": 1}
            },
            "required": ["query"]
        }
    },
    {
        "name": "scrape_web",
        "description": "Fetch, sanitize, and extract clean readable markdown/text from a webpage with hardened SSRF protection.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Target webpage URL to read"},
                "max_length": {"type": "integer", "description": "Maximum characters to extract", "default": 8000}
            },
            "required": ["url"]
        }
    },
    {
        "name": "youtube_transcript",
        "description": "Extract full subtitles/transcript text from any YouTube video URL or ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "video": {"type": "string", "description": "YouTube URL or 11-char Video ID"},
                "languages": {"type": "string", "description": "Priority languages comma-separated (e.g. 'ru,en')", "default": "ru,en"}
            },
            "required": ["video"]
        }
    },
    {
        "name": "calc_expression",
        "description": "Safely evaluate mathematical expressions using an AST sandbox (no eval/exec risk).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Mathematical formula to evaluate (e.g. 'sqrt(144) + 12 * 5')"},
                "precision": {"type": "integer", "description": "Decimal places to round", "default": 4}
            },
            "required": ["expression"]
        }
    },
    {
        "name": "crypto_price",
        "description": "Get real-time spot prices and 24h change for crypto assets (BTC, ETH, SOL, TON, etc.) with dual-engine fallback.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "coins": {"type": "string", "description": "Comma-separated crypto tickers (e.g. 'btc,eth,sol,ton')", "default": "btc,eth,sol,ton"},
                "vs_currency": {"type": "string", "description": "Target fiat currency", "default": "usd"}
            }
        }
    },
    {
        "name": "search_catalog",
        "description": "Search the 2026 Top-50 GitHub AI repositories catalog (Custom Actions, MCP, scraping, agents, automation).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword or topic"},
                "limit": {"type": "integer", "description": "Max items to return", "default": 20}
            }
        }
    },
    {
        "name": "convert_currency",
        "description": "Convert between fiat currencies (USD, EUR, RUB, CNY, KZT) using live or cached exchange rates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "Amount to convert"},
                "from_curr": {"type": "string", "description": "Source currency code (USD, EUR, RUB)"},
                "to_curr": {"type": "string", "description": "Target currency code (USD, EUR, RUB)"}
            },
            "required": ["amount", "from_curr", "to_curr"]
        }
    }
]


async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> str:
    """Route tool invocations to core implementations and return formatted JSON string."""
    if name == "deep_search":
        res = await deep_search(
            query=arguments.get("query", ""),
            num_results=arguments.get("num_results", 5),
            depth=arguments.get("depth", 1)
        )
        return json.dumps(res, ensure_ascii=False, indent=2)
    elif name in ("scrape_web", "scrape_web_page"):
        res = await scrape_web(
            url=arguments.get("url", ""),
            max_length=arguments.get("max_length", 8000)
        )
        return json.dumps(res, ensure_ascii=False, indent=2)
    elif name in ("youtube_transcript", "get_youtube_transcript"):
        res = youtube_transcript(
            video=arguments.get("video", ""),
            languages=arguments.get("languages", "ru,en")
        )
        return json.dumps(res, ensure_ascii=False, indent=2)
    elif name == "calc_expression":
        res = calc_expression(
            expression=arguments.get("expression", ""),
            precision=arguments.get("precision", 4)
        )
        return json.dumps(res, ensure_ascii=False, indent=2)
    elif name in ("crypto_price", "get_crypto_prices"):
        res = await crypto_price(
            coins=arguments.get("coins", "btc,eth,sol,ton"),
            vs_currency=arguments.get("vs_currency", "usd")
        )
        return json.dumps(res, ensure_ascii=False, indent=2)
    elif name == "search_catalog":
        res = search_catalog_2026(
            query=arguments.get("query"),
            limit=arguments.get("limit", 20)
        )
        return json.dumps(res, ensure_ascii=False, indent=2)
    elif name in ("convert_currency", "convert_fiat"):
        res = await convert_fiat(
            amount=float(arguments.get("amount", 1.0)),
            from_curr=arguments.get("from_curr", "USD"),
            to_curr=arguments.get("to_curr", "RUB")
        )
        return json.dumps(res, ensure_ascii=False, indent=2)
    else:
        return json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)


async def run_stdio_server():
    """Cross-platform Model Context Protocol (MCP) JSON-RPC 2.0 stdio server.

    Uses threaded readline to guarantee non-blocking execution across Windows, Linux, and macOS
    without IOCP handle errors or pipe buffering deadlocks.
    """
    loop = asyncio.get_running_loop()

    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            break

        text = line.strip()
        if not text:
            continue

        try:
            req = json.loads(text)
        except Exception as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {str(e)}"}
            }
            sys.stdout.write(json.dumps(err_resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
            continue

        method = req.get("method")
        msg_id = req.get("id")

        if method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "OmniTools-Universal-AI-Bridge",
                        "version": "1.0.0"
                    }
                }
            }
        elif method == "notifications/initialized":
            continue
        elif method == "ping":
            resp = {"jsonrpc": "2.0", "id": msg_id, "result": {}}
        elif method == "tools/list":
            resp = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": TOOLS}
            }
        elif method == "tools/call":
            params = req.get("params", {})
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            try:
                content_text = await handle_call_tool(tool_name, tool_args)
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": content_text}]
                    }
                }
            except Exception as e:
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32603, "message": str(e)}
                }
        else:
            resp = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Method {method} not found"}
            }

        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def main():
    """CLI entrypoint for MCP stdio server."""
    asyncio.run(run_stdio_server())


if __name__ == "__main__":
    main()
