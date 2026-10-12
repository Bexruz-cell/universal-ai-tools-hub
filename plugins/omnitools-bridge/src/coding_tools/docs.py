"""OmniTools Universal AI Bridge - Developer Documentation Retriever

Retrieves official API signatures, module documentation, and standard library references.
Provides offline documentation lookup for Python standard library and core packages.
"""

from __future__ import annotations

import importlib
import inspect
import pydoc
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DocItem(BaseModel):
    title: str
    symbol: str
    docstring: str = ""
    signature: Optional[str] = None
    module: Optional[str] = None
    url: Optional[str] = None


class DocSearchResult(BaseModel):
    query: str
    library: str
    total_results: int
    items: List[DocItem] = Field(default_factory=list)


# Curated offline reference documentation URLs and snippets for common coding topics
KNOWN_DOCS: Dict[str, Dict[str, Any]] = {
    "pytest": {
        "url": "https://docs.pytest.org/en/stable/",
        "summary": "Full-featured Python testing framework supporting fixtures, parametrization, and plugins.",
        "common_symbols": {
            "pytest.mark.parametrize": "Parametrize test function arguments with multiple test inputs.",
            "pytest.fixture": "Decorator to define reusable setup and teardown fixture functions.",
            "pytest.raises": "Context manager to assert that a block of code raises a specified exception.",
            "pytest.mark.skip": "Unconditionally skip a test function or class.",
            "pytest.mark.skipif": "Conditionally skip a test function based on a boolean condition.",
            "pytest.mark.asyncio": "Marker from pytest-asyncio to execute asynchronous test coroutines.",
        }
    },
    "ast": {
        "url": "https://docs.python.org/3/library/ast.html",
        "summary": "Abstract Syntax Tree processing module to parse, inspect, and analyze Python source code.",
        "common_symbols": {
            "ast.parse": "Parse Python source code into an AST node hierarchy.",
            "ast.walk": "Recursively yield all descendant nodes of an AST root node.",
            "ast.NodeVisitor": "Base class for AST visitors that implement visit_<NodeType> methods.",
            "ast.unparse": "Convert an AST node back into a formatted Python source code string.",
        }
    },
    "pathlib": {
        "url": "https://docs.python.org/3/library/pathlib.html",
        "summary": "Object-oriented filesystem paths with platform-specific semantics.",
        "common_symbols": {
            "Path.resolve": "Resolve canonical absolute path, eliminating symlinks and relative references.",
            "Path.is_relative_to": "Determine if a path is contained within a base directory path (Python 3.9+).",
            "Path.read_text": "Read entire file contents as decoded text.",
            "Path.write_text": "Write text string to file atomically.",
        }
    },
    "asyncio": {
        "url": "https://docs.python.org/3/library/asyncio.html",
        "summary": "Asynchronous I/O, event loop, and coroutine execution framework.",
        "common_symbols": {
            "asyncio.run": "Execute a coroutine and return its result, managing event loop lifecycle.",
            "asyncio.to_thread": "Run a blocking synchronous function in a separate worker thread.",
            "asyncio.gather": "Run concurrent awaitable tasks and gather their results.",
        }
    },
    "pydantic": {
        "url": "https://docs.pydantic.dev/latest/",
        "summary": "Data validation and settings management using Python type hints.",
        "common_symbols": {
            "BaseModel": "Primary class for defining structured data models with type validation.",
            "Field": "Function for configuring validation rules, default values, and metadata for model attributes.",
            "model_dump": "Convert a Pydantic v2 model instance into a standard dictionary.",
        }
    },
    "fastapi": {
        "url": "https://fastapi.tiangolo.com/",
        "summary": "High-performance ASGI web framework for building modern REST APIs with OpenAPI.",
        "common_symbols": {
            "FastAPI": "Primary application instance to register HTTP router endpoints and middleware.",
            "APIRouter": "Modular router to group related REST endpoints.",
            "HTTPException": "Exception class to return HTTP status codes and structured detail errors.",
        }
    }
}


def find_documentation(
    query: str,
    library: Optional[str] = None,
    max_results: int = 5,
) -> Dict[str, Any]:
    """MCP Tool #14 entry point: search official programming documentation and signatures."""
    items: List[DocItem] = []
    lib_target = (library or "").strip().lower()
    q_lower = query.strip().lower()

    # 1. Search in curated known library documentation
    for lib_key, lib_info in KNOWN_DOCS.items():
        if lib_target and lib_target != lib_key and lib_key not in lib_target:
            continue
        for sym_name, sym_doc in lib_info.get("common_symbols", {}).items():
            if q_lower in sym_name.lower() or q_lower in sym_doc.lower() or not q_lower:
                items.append(DocItem(
                    title=sym_name,
                    symbol=sym_name,
                    docstring=sym_doc,
                    module=lib_key,
                    url=lib_info.get("url"),
                ))
                if len(items) >= max_results:
                    break
        if len(items) >= max_results:
            break

    # 2. Live introspection fallback for standard library or installed packages
    if len(items) < max_results:
        search_targets = [library] if library else [query.split(".")[0]]
        for target in search_targets:
            if not target:
                continue
            try:
                mod = importlib.import_module(target)
                doc = inspect.getdoc(mod) or ""
                items.append(DocItem(
                    title=f"Module {target}",
                    symbol=target,
                    docstring=doc[:400] + ("..." if len(doc) > 400 else ""),
                    module=target,
                ))
            except Exception:
                pass

    return {
        "query": query,
        "library": library or "auto",
        "total_results": len(items),
        "items": [it.model_dump() for it in items],
    }
