import sys
import json
import asyncio
from pathlib import Path

# Add project root
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.core.tools import (
    search_catalog_2026,
    scrape_web_page,
    get_youtube_transcript,
    get_crypto_prices,
    convert_fiat
)

TOOLS = [
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
        "name": "scrape_web",
        "description": "Fetch and extract clean readable text from any website URL for analysis.",
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
        "name": "get_youtube_transcript",
        "description": "Extract full subtitles/transcript text from any YouTube video URL or ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "video": {"type": "string", "description": "YouTube video URL or 11-char video ID"},
                "languages": {"type": "string", "description": "Languages comma-separated, e.g. ru,en", "default": "ru,en"}
            },
            "required": ["video"]
        }
    },
    {
        "name": "get_crypto_prices",
        "description": "Get real-time cryptocurrency prices, 24h change, and market tickers without API keys.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "coins": {"type": "string", "description": "Tickers comma-separated (btc,eth,sol,ton,trx)", "default": "btc,eth,sol,ton"}
            }
        }
    },
    {
        "name": "convert_currency",
        "description": "Real-time fiat currency converter (USD, EUR, RUB, CNY, KZT).",
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

async def handle_call_tool(name: str, arguments: dict):
    if name == "search_catalog":
        res = search_catalog_2026(query=arguments.get("query"), limit=arguments.get("limit", 20))
        return json.dumps(res, ensure_ascii=False, indent=2)
    elif name == "scrape_web":
        res = await scrape_web_page(url=arguments["url"], max_length=arguments.get("max_length", 8000))
        return json.dumps(res, ensure_ascii=False, indent=2)
    elif name == "get_youtube_transcript":
        res = get_youtube_transcript(video=arguments["video"], languages=arguments.get("languages", "ru,en"))
        return json.dumps(res, ensure_ascii=False, indent=2)
    elif name == "get_crypto_prices":
        res = await get_crypto_prices(coins=arguments.get("coins", "btc,eth,sol,ton"))
        return json.dumps(res, ensure_ascii=False, indent=2)
    elif name == "convert_currency":
        res = await convert_fiat(amount=float(arguments["amount"]), from_curr=arguments["from_curr"], to_curr=arguments["to_curr"])
        return json.dumps(res, ensure_ascii=False, indent=2)
    else:
        return f"Unknown tool: {name}"

async def run_stdio_server():
    """Standard Model Context Protocol (MCP) JSON-RPC 2.0 stdio server."""
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    w_transport, w_protocol = await loop.connect_write_pipe(asyncio.streams.FlowControlMixin, sys.stdout)
    writer = asyncio.StreamWriter(w_transport, w_protocol, reader, loop)

    while True:
        line = await reader.readline()
        if not line:
            break
        text = line.decode("utf-8").strip()
        if not text:
            continue
        try:
            req = json.loads(text)
        except Exception:
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
                        "name": "OmniTools-Universal-AI-Hub",
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

        out_line = json.dumps(resp, ensure_ascii=False) + "\n"
        sys.stdout.write(out_line)
        sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(run_stdio_server())
