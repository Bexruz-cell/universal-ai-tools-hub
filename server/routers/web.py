from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, HttpUrl
import httpx
from bs4 import BeautifulSoup
import re

router = APIRouter(prefix="/web", tags=["Web Tools"])

class ScrapedPageResponse(BaseModel):
    url: str
    title: str
    description: str
    text_content: str
    character_count: int

@router.get("/scrape", response_model=ScrapedPageResponse, summary="Extract clean text from any URL")
async def scrape_url(
    url: str = Query(..., description="Target webpage URL to read and parse"),
    max_length: int = Query(8000, description="Maximum characters of text to return")
):
    """
    Scrapes any web page URL, strips away HTML boilerplate, advertisements,
    scripts and styling, and returns clean readable markdown/text for ChatGPT.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code >= 400:
                raise HTTPException(status_code=resp.status_code, detail=f"Web page returned HTTP {resp.status_code}")
            html_text = resp.text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch webpage: {str(e)}")

    soup = BeautifulSoup(html_text, "html.parser")

    # Remove script, style, nav, footer, header
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "aside"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else "No Title"
    
    desc_meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    description = desc_meta.get("content", "").strip() if desc_meta else ""

    text = soup.get_text(separator="\n")
    # Clean whitespace
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    clean_text = "\n".join(lines)[:max_length]

    return ScrapedPageResponse(
        url=url,
        title=title,
        description=description,
        text_content=clean_text,
        character_count=len(clean_text)
    )
