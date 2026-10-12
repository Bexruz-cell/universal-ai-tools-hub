from fastapi import APIRouter, Query
from typing import List, Optional
import json
from pathlib import Path
from pydantic import BaseModel

router = APIRouter(prefix="/catalog", tags=["Catalog"])

class RepositoryItem(BaseModel):
    id: int
    name: str
    repo_slug: str
    github_url: str
    description: str
    chatgpt_use_case: str

def load_catalog() -> List[dict]:
    catalog_path = Path(__file__).resolve().parent.parent.parent / "catalog" / "catalog.json"
    if not catalog_path.exists():
        return []
    with open(catalog_path, "r", encoding="utf-8") as f:
        return json.load(f)

@router.get("", response_model=List[RepositoryItem], summary="Get Top-50 Repositories for ChatGPT")
def get_catalog(
    query: Optional[str] = Query(None, description="Search keyword in name or description"),
    limit: int = Query(50, ge=1, le=50, description="Number of results to return")
):
    """
    Returns curated list of top GitHub repositories for ChatGPT Custom Actions,
    plugins, agents, and automation tools.
    """
    items = load_catalog()
    if query:
        q = query.lower()
        items = [
            i for i in items
            if q in i["name"].lower() or q in i["description"].lower() or q in i["chatgpt_use_case"].lower()
        ]
    return items[:limit]
