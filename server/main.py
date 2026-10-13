from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from server.routers import catalog, web, finance

app = FastAPI(
    title="ChatGPT SuperActions Hub API",
    description="Production-ready multi-tool API for ChatGPT Custom GPT Actions, autonomous agents, and web integrations.",
    version="1.0.0",
    servers=[
        {"url": "http://localhost:8000", "description": "Local development server"}
    ]
)

# Enable CORS for ChatGPT and local web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://chat.openai.com", "https://chatgpt.com", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(catalog.router, prefix="/api/v1")
app.include_router(web.router, prefix="/api/v1")
app.include_router(finance.router, prefix="/api/v1")

@app.get("/", summary="Root Health Check")
def root():
    return {
        "status": "online",
        "service": "ChatGPT SuperActions Hub API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "openapi_url": "/openapi.json"
    }

@app.get("/health", summary="Health Status")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)
