"""OmniTools Universal AI Bridge - Model Context Protocol (MCP) Stdio Server.

Fully compliant with MCP Specification (2024-11-05).
Cross-platform stdio JSON-RPC 2.0 communication supporting Windows, Linux, and macOS.
Wires 15 coding tools with token bounding and preserves backwards compatibility for legacy tools.
"""

from __future__ import annotations

import asyncio
import json
import os
import queue
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Ensure UTF-8 streams across all operating systems
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

# Dynamically add project root and src directory
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
src_dir = current_dir.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# ---------------------------------------------------------------------------
# Imports: 15 Coding Tools Engine Modules
# ---------------------------------------------------------------------------
from src.coding_tools.repo_map import generate_repo_map
from src.coding_tools.search import search_code
from src.coding_tools.symbols import read_symbol, find_references
from src.coding_tools.deps import dependency_graph
from src.coding_tools.patcher import propose_patch, apply_patch
from src.coding_tools.test_runner import run_targeted_tests, verify_changes, resolve_test_targets
from src.coding_tools.checkpoints import git_checkpoint
from src.coding_tools.diagnostics import diagnose_error
from src.coding_tools.docs import find_documentation
from src.coding_tools.catalog import search_coding_catalog
from src.context_optimizer.compressor import summarize_context
from src.context_optimizer.budget import estimate_tokens
from src.security.workspace_policy import WorkspacePolicy


def _authorize_path(policy: WorkspacePolicy, value: Any, **kwargs: Any) -> str:
    """Validate a tool path against process-authorized roots."""
    return str(policy.validate(value, **kwargs))


def _authorize_tool_arguments(name: str, arguments: Dict[str, Any], policy: WorkspacePolicy) -> Dict[str, Any]:
    """Normalize and authorize every filesystem-bearing MCP argument."""
    args = dict(arguments)
    if name == "repo_map":
        args["root_path"] = _authorize_path(policy, args.get("root_path", "."), must_be_dir=True)
    elif name == "search_code":
        args["path"] = _authorize_path(policy, args.get("path", "."))
    elif name == "read_symbol":
        args["file_path"] = _authorize_path(policy, args.get("file_path"), must_be_file=True)
    elif name == "find_references":
        args["workspace_root"] = _authorize_path(policy, args.get("workspace_root", "."), must_be_dir=True)
    elif name == "dependency_graph":
        args["file_path"] = _authorize_path(policy, args.get("file_path", "src/adapters/mcp_adapter.py"), must_be_file=True)
        if args.get("workspace_root"):
            args["workspace_root"] = _authorize_path(policy, args["workspace_root"], must_be_dir=True)
    elif name in {"propose_patch", "apply_patch"}:
        args["file_path"] = _authorize_path(policy, args.get("file_path"), allow_nonexistent=name == "propose_patch")
    elif name == "summarize_context":
        source = args.get("source", ".")
        # summarize_context accepts both inline source text and a file path.
        # Only path-shaped inputs are authorized; inline content must remain data.
        if isinstance(source, (str, Path)) and "\n" not in str(source):
            candidate = Path(str(source))
            if candidate.is_absolute() or candidate.exists() or "/" in str(source) or "\\" in str(source):
                args["source"] = _authorize_path(policy, source, must_be_file=True)
    elif name == "estimate_tokens":
        args["file_paths"] = [_authorize_path(policy, path, must_be_file=True) for path in args.get("file_paths", [])]
    elif name == "diagnose_error":
        args["related_files"] = [_authorize_path(policy, path, must_be_file=True) for path in args.get("related_files", [])]
    elif name in {"run_targeted_tests", "verify_changes"}:
        if args.get("changed_files"):
            args["changed_files"] = [_authorize_path(policy, path, must_be_file=True) for path in args["changed_files"]]
        if args.get("modified_files"):
            args["modified_files"] = [_authorize_path(policy, path, must_be_file=True) for path in args["modified_files"]]
        targets = args.get("targets") or ([] if not args.get("test_target") else [args["test_target"]])
        checked_targets = []
        for target in targets:
            target_text = str(target).split("::", 1)[0]
            checked_targets.append(str(policy.validate(target_text, must_be_file=True)) + (str(target)[len(target_text):] if "::" in str(target) else ""))
        if targets:
            args["targets"] = checked_targets
        if args.get("test_target"):
            target_text = str(args["test_target"]).split("::", 1)[0]
            args["test_target"] = str(policy.validate(target_text, must_be_file=True)) + str(args["test_target"])[len(target_text):]
        if args.get("test_targets"):
            checked = []
            for target in args["test_targets"]:
                target_text = str(target).split("::", 1)[0]
                checked.append(str(policy.validate(target_text, must_be_file=True)) + str(target)[len(target_text):])
            args["test_targets"] = checked
    elif name == "git_checkpoint":
        # The checkpoint implementation derives the repository from process cwd;
        # authorize that implicit scope before any git subprocess is started.
        policy.validate(Path.cwd(), must_be_dir=True)
    return args

# ---------------------------------------------------------------------------
# Imports: Legacy Tools Engine (Backwards Compatibility)
# ---------------------------------------------------------------------------
from src.core.tools import (
    deep_search,
    scrape_web,
    youtube_transcript,
    calc_expression,
    crypto_price,
    search_catalog_2026,
    convert_fiat,
)

# ==============================================================================
# MCP Tool Schemas (15 Coding Tools + Backwards Compatibility Tools)
# ==============================================================================

TOOLS: List[Dict[str, Any]] = [
    # -------------------------------------------------------------------------
    # 15 AI Coding Tools
    # -------------------------------------------------------------------------
    {
        "name": "repo_map",
        "description": "Generate a compact, token-bounded repository directory layout, file statistics, and architecture outline.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root_path": {"type": "string", "description": "Repository root path", "default": "."},
                "max_depth": {"type": "integer", "description": "Maximum directory traversal depth", "default": 3},
                "max_entries": {"type": "integer", "description": "Maximum file tree entries", "default": 150},
                "show_sizes": {"type": "boolean", "description": "Include formatted byte sizes in tree", "default": True},
                "as_format": {"type": "string", "enum": ["text", "markdown", "dict"], "description": "Output representation format", "default": "dict"}
            }
        }
    },
    {
        "name": "search_code",
        "description": "Fast regex and literal code search across repository using ripgrep with Python fallback and token bounding.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Search pattern or query keyword"},
                "path": {"type": "string", "description": "Search root path", "default": "."},
                "regex": {"type": "boolean", "description": "Whether pattern is regular expression", "default": False},
                "case_sensitive": {"type": "boolean", "description": "Match case sensitively", "default": False},
                "max_results": {"type": "integer", "description": "Maximum match items to return", "default": 25},
                "file_pattern": {"type": "string", "description": "Glob filter (e.g. '*.py')"}
            },
            "required": ["pattern"]
        }
    },
    {
        "name": "read_symbol",
        "description": "Extract AST-based symbol definition (function or class) with docstring and body without reading full files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol_name": {"type": "string", "description": "Target symbol or qualified name (e.g. 'Calculator.compute')"},
                "file_path": {"type": "string", "description": "Path to Python source file"},
                "max_body_lines": {"type": "integer", "description": "Maximum lines of implementation body to extract", "default": 200}
            },
            "required": ["symbol_name", "file_path"]
        }
    },
    {
        "name": "find_references",
        "description": "Scan workspace for symbol definitions, imports, and usages using AST analysis and regex fallback.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol_name": {"type": "string", "description": "Symbol name to trace usages for"},
                "workspace_root": {"type": "string", "description": "Root path to search within", "default": "."},
                "max_results": {"type": "integer", "description": "Maximum reference sites to return", "default": 30}
            },
            "required": ["symbol_name"]
        }
    },
    {
        "name": "dependency_graph",
        "description": "Analyze module import dependencies, internal/external packages, and compute affected test targets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Target file to map dependencies for", "default": "src/adapters/mcp_adapter.py"},
                "depth": {"type": "integer", "description": "Maximum dependency traversal depth", "default": 2},
                "include_external": {"type": "boolean", "description": "Include third-party package dependencies", "default": True}
            }
        }
    },
    {
        "name": "propose_patch",
        "description": "Generate a unified diff preview and patch proposal. Strictly read-only; never touches disk.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Target file path"},
                "instruction": {"type": "string", "description": "Summary of proposed change"},
                "new_content": {"type": "string", "description": "Full proposed replacement content for file"},
                "patch_diff": {"type": "string", "description": "Direct unified diff string to apply"},
                "target_content": {"type": "string", "description": "Exact text block in target file to replace"},
                "replacement_content": {"type": "string", "description": "New replacement text block"}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "apply_patch",
        "description": "Apply proposed patch safely with pre-write backup (.bak), atomic write, and auto-rollback on syntax failure.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to file to patch"},
                "patch_id": {"type": "string", "description": "Optional cached proposal ID from propose_patch"},
                "new_content": {"type": "string", "description": "Full new content to write"},
                "patch_diff": {"type": "string", "description": "Unified diff to apply"},
                "target_content": {"type": "string", "description": "Exact block in target file to replace"},
                "replacement_content": {"type": "string", "description": "New text block"},
                "dry_run": {"type": "boolean", "description": "Simulate patch application without disk modification", "default": False},
                "run_syntax_check": {"type": "boolean", "description": "Enforce syntax gate after applying", "default": True}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "run_targeted_tests",
        "description": "Execute targeted pytest test suite with timeouts, isolated process environments, and bounded logs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "targets": {"type": "array", "items": {"type": "string"}, "description": "List of test files or node IDs"},
                "test_target": {"type": "string", "description": "Single test target file or node ID"},
                "modified_files": {"type": "array", "items": {"type": "string"}, "description": "Auto-resolve test targets from modified files"},
                "pytest_args": {"type": "array", "items": {"type": "string"}, "description": "Extra pytest flags (e.g. ['-q', '-x'])"}
            }
        }
    },
    {
        "name": "verify_changes",
        "description": "Run the complete verification gate: py_compile syntax validation, targeted tests, and regression check.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "changed_files": {"type": "array", "items": {"type": "string"}, "description": "List of modified files to compile and verify"},
                "test_targets": {"type": "array", "items": {"type": "string"}, "description": "Specific test targets to execute"}
            }
        }
    },
    {
        "name": "summarize_context",
        "description": "Produce concise symbol outlines, key signatures, and interfaces for token-efficient agent handoffs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Source file path, directory path, or code string", "default": "."},
                "max_tokens": {"type": "integer", "description": "Target token budget ceiling", "default": 600},
                "output_format": {"type": "string", "enum": ["stub", "markdown", "json"], "default": "markdown"}
            }
        }
    },
    {
        "name": "estimate_tokens",
        "description": "Accurately estimate token consumption for text or files using tiktoken or multi-script heuristics.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text content to evaluate"},
                "file_paths": {"type": "array", "items": {"type": "string"}, "description": "Files to read and measure tokens for"},
                "model": {"type": "string", "description": "Target tokenizer model", "default": "gpt-4o"}
            }
        }
    },
    {
        "name": "git_checkpoint",
        "description": "Create instant, lightweight git tags/snapshots as safe rollback checkpoints before code changes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["create", "diff", "rollback", "list", "get", "delete"], "default": "create"},
                "name": {"type": "string", "description": "Checkpoint name or tag identifier"},
                "message": {"type": "string", "description": "Checkpoint description or commit note"},
                "checkpoint_id": {"type": "string", "description": "Target checkpoint ID for rollback or inspection"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "diagnose_error",
        "description": "Parse error tracebacks or compiler logs, pinpoint origin file and line, and generate surgical fix recommendations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "error_traceback": {"type": "string", "description": "Full error traceback or compiler output"},
                "related_files": {"type": "array", "items": {"type": "string"}, "description": "Suspected file paths"},
                "suggest_fix": {"type": "boolean", "description": "Include targeted fix suggestion", "default": True}
            },
            "required": ["error_traceback"]
        }
    },
    {
        "name": "find_documentation",
        "description": "Search official programming documentation, standard library APIs, and module docstrings.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "API name, function signature, or search term"},
                "library": {"type": "string", "description": "Library or module name (e.g. 'pytest', 'ast', 'asyncio')"},
                "max_results": {"type": "integer", "description": "Maximum documentation snippets", "default": 5}
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_coding_catalog",
        "description": "Search the curated 50-repository 2026 AI coding database by query keyword, category, and use case.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword or repository name"},
                "category": {"type": "string", "description": "Category filter code or name"},
                "limit": {"type": "integer", "description": "Maximum items to return", "default": 20}
            }
        }
    },

    # -------------------------------------------------------------------------
    # Backwards Compatibility Tools (Preserved for tests & existing clients)
    # -------------------------------------------------------------------------
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
        "description": "Search the 2026 Top-50 GitHub AI repositories catalog.",
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


# ==============================================================================
# Tool Execution Router
# ==============================================================================

async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> str:
    """Route tool invocations to core implementations and return formatted JSON string."""
    try:
        arguments = _authorize_tool_arguments(name, arguments, WorkspacePolicy.from_process())
        # 1. repo_map
        if name == "repo_map":
            root_path = arguments.get("root_path", ".")
            max_depth = int(arguments.get("max_depth", 3))
            max_entries = int(arguments.get("max_entries", 150))
            show_sizes = bool(arguments.get("show_sizes", True))
            as_format = arguments.get("as_format", "dict")
            res = generate_repo_map(
                root_path=root_path,
                max_depth=max_depth,
                max_entries=max_entries,
                show_sizes=show_sizes,
                as_format=as_format if as_format in ("text", "markdown", "dict") else "dict"
            )
            if isinstance(res, (dict, list)):
                return json.dumps(res, ensure_ascii=False, indent=2)
            return str(res)

        # 2. search_code
        elif name == "search_code":
            query = arguments.get("pattern") or arguments.get("query", "")
            path = arguments.get("path", ".")
            regex = bool(arguments.get("regex", False))
            case_sensitive = bool(arguments.get("case_sensitive", False))
            max_results = int(arguments.get("max_results", 25))
            file_pattern = arguments.get("file_pattern")
            include_patterns = [file_pattern] if file_pattern and file_pattern != "*" else None
            res = search_code(
                query=query,
                path=path,
                regex=regex,
                case_sensitive=case_sensitive,
                max_results=max_results,
                include_patterns=include_patterns
            )
            return json.dumps(res, ensure_ascii=False, indent=2)

        # 3. read_symbol
        elif name == "read_symbol":
            symbol_name = arguments.get("symbol_name", "")
            file_path = arguments.get("file_path", "")
            max_body_lines = int(arguments.get("max_body_lines", arguments.get("context_lines", 200)))
            res = read_symbol(file_path=file_path, symbol_name=symbol_name, max_body_lines=max_body_lines)
            return json.dumps(res, ensure_ascii=False, indent=2)

        # 4. find_references
        elif name == "find_references":
            symbol_name = arguments.get("symbol_name", "")
            workspace_root = arguments.get("workspace_root", arguments.get("path", "."))
            max_results = int(arguments.get("max_results", 30))
            res = find_references(symbol_name=symbol_name, workspace_root=workspace_root, max_results=max_results)
            return json.dumps(res, ensure_ascii=False, indent=2)

        # 5. dependency_graph
        elif name == "dependency_graph":
            file_path = arguments.get("file_path", arguments.get("entry_point", "src/adapters/mcp_adapter.py"))
            depth = int(arguments.get("depth", arguments.get("max_depth", 2)))
            workspace_root = arguments.get("workspace_root")
            res = dependency_graph(file_path=file_path, depth=depth, workspace_root=workspace_root)
            return json.dumps(res, ensure_ascii=False, indent=2)

        # 6. propose_patch
        elif name == "propose_patch":
            file_path = arguments.get("file_path", "")
            new_content = arguments.get("new_content") or arguments.get("replacement_content")
            patch_diff = arguments.get("patch_diff") or arguments.get("unified_diff")
            target_content = arguments.get("target_content")
            if target_content is not None and new_content is not None and not patch_diff and file_path:
                try:
                    existing = WorkspacePolicy.from_process().guard.safe_read_text(file_path)
                    new_content = existing.replace(target_content, new_content)
                except Exception:
                    pass
            res = propose_patch(file_path=file_path, new_content=new_content, patch_diff=patch_diff)
            return json.dumps(res.to_dict(), ensure_ascii=False, indent=2)

        # 7. apply_patch
        elif name == "apply_patch":
            file_path = arguments.get("file_path")
            patch_id = arguments.get("patch_id")
            new_content = arguments.get("new_content") or arguments.get("replacement_content")
            patch_diff = arguments.get("patch_diff") or arguments.get("diff") or arguments.get("unified_diff")
            target_content = arguments.get("target_content")
            if file_path and target_content is not None and new_content is not None and not patch_diff:
                try:
                    existing = WorkspacePolicy.from_process().guard.safe_read_text(file_path)
                    new_content = existing.replace(target_content, new_content)
                except Exception:
                    pass
            dry_run = bool(arguments.get("dry_run", False))
            confirm = bool(arguments.get("confirm", not dry_run))
            res = apply_patch(
                file_path=file_path,
                new_content=new_content,
                patch_diff=patch_diff,
                patch_id=patch_id,
                confirm=confirm,
                raise_errors=False
            )
            return json.dumps(res.to_dict(), ensure_ascii=False, indent=2)

        # 8. run_targeted_tests
        elif name == "run_targeted_tests":
            targets = arguments.get("targets")
            test_target = arguments.get("test_target")
            if not targets and test_target:
                targets = [test_target]
            elif not targets and arguments.get("modified_files"):
                targets = resolve_test_targets(arguments.get("modified_files"))
            pytest_args = arguments.get("pytest_args")
            res = run_targeted_tests(targets=targets, pytest_args=pytest_args)
            return json.dumps(res.to_dict(), ensure_ascii=False, indent=2)

        # 9. verify_changes
        elif name == "verify_changes":
            changed_files = arguments.get("changed_files") or arguments.get("modified_files", [])
            if not changed_files and arguments.get("file_path"):
                changed_files = [arguments["file_path"]]
            test_targets = arguments.get("test_targets")
            res = verify_changes(changed_files=changed_files, test_targets=test_targets)
            return json.dumps(res.to_dict(), ensure_ascii=False, indent=2)

        # 10. summarize_context
        elif name == "summarize_context":
            source = arguments.get("source") or arguments.get("active_files") or "."
            max_tokens = arguments.get("max_tokens") or arguments.get("token_budget", 600)
            output_format = arguments.get("output_format", "markdown")
            res = summarize_context(source=source, max_tokens=max_tokens, output_format=output_format)
            return json.dumps(res.to_dict(), ensure_ascii=False, indent=2)

        # 11. estimate_tokens
        elif name == "estimate_tokens":
            content = arguments.get("text") or arguments.get("content", "")
            file_paths = arguments.get("file_paths", [])
            if file_paths and not content:
                pieces = []
                for fp in file_paths:
                    try:
                        pieces.append(WorkspacePolicy.from_process().guard.safe_read_text(fp))
                    except Exception:
                        pass
                content = "\n".join(pieces)
            model = arguments.get("model", "gpt-4o")
            tokens_count = estimate_tokens(content, model=model)
            return json.dumps({"tokens": tokens_count, "model": model, "length_chars": len(content) if isinstance(content, str) else 0}, ensure_ascii=False, indent=2)

        # 12. git_checkpoint
        elif name == "git_checkpoint":
            action = arguments.get("action", "create")
            chk_name = arguments.get("name") or arguments.get("checkpoint_name")
            message = arguments.get("message")
            checkpoint_id = arguments.get("checkpoint_id")
            res = git_checkpoint(action=action, name=chk_name, message=message, checkpoint_id=checkpoint_id)
            return json.dumps(res, ensure_ascii=False, indent=2)

        # 13. diagnose_error
        elif name == "diagnose_error":
            error_traceback = arguments.get("error_traceback", "")
            related_files = arguments.get("related_files")
            suggest_fix = bool(arguments.get("suggest_fix", True))
            res = diagnose_error(error_traceback=error_traceback, related_files=related_files, suggest_fix=suggest_fix)
            return json.dumps(res, ensure_ascii=False, indent=2)

        # 14. find_documentation
        elif name == "find_documentation":
            query = arguments.get("query", "")
            library = arguments.get("library")
            max_results = int(arguments.get("max_results", 5))
            res = find_documentation(query=query, library=library, max_results=max_results)
            return json.dumps(res, ensure_ascii=False, indent=2)

        # 15. search_coding_catalog
        elif name == "search_coding_catalog":
            query = arguments.get("query", "")
            category = arguments.get("category")
            limit = int(arguments.get("limit", 20))
            res = search_coding_catalog(query=query, category=category, limit=limit)
            return json.dumps(res, ensure_ascii=False, indent=2)

        # ---------------------------------------------------------------------
        # Backwards Compatibility Routing
        # ---------------------------------------------------------------------
        elif name == "deep_search":
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
            # For backward compatibility with tests expecting a list return
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

    except Exception as e:
        message = str(e)
        error_code = "WORKSPACE_ACCESS_DENIED" if any(
            marker in message.lower()
            for marker in ("workspace", "outside authorized", "path traversal", "symlink", "reparse")
        ) else "TOOL_EXECUTION_ERROR"
        return json.dumps(
            {
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": message,
                    "tool": name,
                    "retryable": False,
                },
            },
            ensure_ascii=False,
        )


# ==============================================================================
# Model Context Protocol JSON-RPC 2.0 Stdio Server
# ==============================================================================

def run_stdio_server():
    """Cross-platform Model Context Protocol (MCP) JSON-RPC 2.0 stdio server.

    Uses a dedicated blocking stdin reader and a synchronous transport loop so
    tool execution is not coupled to Windows asyncio self-pipe initialization.
    """
    input_queue: queue.Queue[str | None] = queue.Queue()

    def read_stdin() -> None:
        try:
            for input_line in sys.stdin:
                input_queue.put(input_line)
        finally:
            input_queue.put(None)

    threading.Thread(target=read_stdin, name="mcp-stdin-reader", daemon=True).start()

    while True:
        line = input_queue.get()
        if line is None:
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
                        "version": "2.1.0"
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
                content_text = asyncio.run(handle_call_tool(tool_name, tool_args))
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": content_text}]
                    }
                }
            except Exception as e:
                error_text = str(e).lower()
                error_code = "WORKSPACE_ACCESS_DENIED" if "workspace" in error_text or "outside authorized" in error_text or "path traversal" in error_text else "TOOL_EXECUTION_ERROR"
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32603, "message": str(e), "data": {"error_code": error_code, "retryable": False}}
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
    run_stdio_server()


if __name__ == "__main__":
    main()

