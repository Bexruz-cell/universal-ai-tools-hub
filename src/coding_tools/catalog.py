"""OmniTools Universal AI Bridge - Curated 50 Coding Repositories Search Engine

Loads and filters the 2026 Top-50 coding repository catalog (catalog/top_50_coding_repositories_2026.json)
by keyword, category code, and technical capabilities.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RepoItem(BaseModel):
    id: int
    name: str
    github_url: str
    category: str
    category_code: str
    category_name: str
    description: str
    coding_use_case: str
    capabilities: List[str] = Field(default_factory=list)
    license: str
    availability_status: str


def search_coding_catalog(
    query: str = "",
    category: Optional[str] = None,
    limit: int = 20,
    catalog_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """MCP Tool #15 entry point: search curated 50 coding repositories."""
    cat_file = Path(catalog_path) if catalog_path else Path(__file__).resolve().parent.parent.parent / "catalog" / "top_50_coding_repositories_2026.json"
    
    if not cat_file.is_file():
        # Fallback to local plugins copy
        cat_file = Path(__file__).resolve().parent.parent.parent / "plugins" / "omnitools-bridge" / "catalog" / "top_50_coding_repositories_2026.json"

    if not cat_file.is_file():
        return {
            "status": "error",
            "message": f"Catalog file not found at {cat_file}",
            "total": 0,
            "repositories": [],
        }

    try:
        data: List[Dict[str, Any]] = json.loads(cat_file.read_text(encoding="utf-8"))
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to parse catalog JSON: {e}",
            "total": 0,
            "repositories": [],
        }

    q = (query or "").strip().lower()
    cat_filter = (category or "").strip().lower()

    matches = []
    for item in data:
        # Category filter
        item_cat = (item.get("category", "") + " " + item.get("category_code", "") + " " + item.get("category_name", "")).lower()
        if cat_filter and cat_filter != "all" and cat_filter not in item_cat:
            continue

        # Query filter
        if q:
            name_match = q in item.get("name", "").lower()
            desc_match = q in item.get("description", "").lower()
            use_match = q in item.get("coding_use_case", "").lower() or q in item.get("use_case", "").lower()
            caps_match = any(q in c.lower() for c in item.get("capabilities", []))
            if not (name_match or desc_match or use_match or caps_match):
                continue

        matches.append(item)
        if len(matches) >= limit:
            break

    return {
        "status": "success",
        "query": query,
        "category_filter": category or "all",
        "total": len(matches),
        "total_catalog": len(data),
        "repositories": matches,
    }
