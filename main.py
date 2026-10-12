import argparse
import sys
import asyncio

def run():
    parser = argparse.ArgumentParser(description="OmniTools Universal AI Bridge Launcher")
    parser.add_argument(
        "--mode",
        choices=["api", "mcp", "test"],
        default="api",
        help="Target runtime: 'api' for ChatGPT/Codex REST & OpenAPI, 'mcp' for Claude & Antigravity MCP, 'test' to run test suite"
    )
    parser.add_argument("--host", default="0.0.0.0", help="API bind host")
    parser.add_argument("--port", type=int, default=8000, help="API bind port")
    args = parser.parse_args()

    if args.mode == "mcp":
        from src.adapters.mcp_adapter import run_stdio_server
        print("Starting MCP Stdio Server (for Claude and Antigravity)...", file=sys.stderr)
        asyncio.run(run_stdio_server())
    elif args.mode == "test":
        import pytest
        sys.exit(pytest.main(["tests/", "-v"]))
    else:
        import uvicorn
        print(f"Starting FastAPI & OpenAPI Server (for ChatGPT & Codex) on {args.host}:{args.port}...", file=sys.stderr)
        uvicorn.run("src.adapters.api_adapter:app", host=args.host, port=args.port, reload=False)

if __name__ == "__main__":
    run()
