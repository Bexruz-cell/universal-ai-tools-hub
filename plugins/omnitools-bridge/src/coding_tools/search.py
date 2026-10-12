"""High-Performance Code Search Engine.

Supports fast search using ripgrep subprocess where available,
with pure Python regex fallback when ripgrep is unavailable or encounters errors.
Features token bloat defense, strict line bounding, and configurable result limits.
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


DEFAULT_IGNORED_DIRS: Set[str] = {
    ".git",
    ".svn",
    ".hg",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "env",
    "node_modules",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "target",
    ".eggs",
}

DEFAULT_IGNORED_EXTS: Set[str] = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dll",
    ".dylib",
    ".exe",
    ".bin",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".rar",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".webp",
    ".mp4",
    ".mp3",
    ".wav",
    ".db",
    ".sqlite",
    ".sqlite3",
}

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


@dataclass
class SearchMatch:
    file: str
    line_number: int
    column: Optional[int]
    content: str
    truncated: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _find_ripgrep() -> Optional[str]:
    """Locate ripgrep executable on system PATH."""
    return shutil.which("rg")


def _truncate_line(line: str, max_line_length: int) -> tuple[str, bool]:
    """Truncate line to prevent context and token bloat."""
    if len(line) > max_line_length:
        omitted = len(line) - max_line_length
        return f"{line[:max_line_length]}... [truncated: {omitted} chars omitted]", True
    return line, False


def _is_binary(file_path: Path) -> bool:
    """Check if file appears to be binary by scanning first 1024 bytes for null bytes."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            return b"\x00" in chunk
    except OSError:
        return True


def _search_ripgrep(
    query: str,
    target_path: Path,
    regex: bool,
    case_sensitive: bool,
    max_results: int,
    max_line_length: int,
    timeout_seconds: float,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Execute search using ripgrep subprocess with JSON streaming parsing."""
    rg_bin = _find_ripgrep()
    if not rg_bin:
        return None

    cmd: List[str] = [
        rg_bin,
        "--json",
        "--line-number",
        "--column",
        "--color=never",
    ]

    if not case_sensitive:
        cmd.append("-i")
    else:
        cmd.append("-s")

    if not regex:
        cmd.append("-F")

    if include_patterns:
        for pat in include_patterns:
            cmd.extend(["-g", pat])

    if exclude_patterns:
        for pat in exclude_patterns:
            cmd.extend(["-g", f"!{pat}"])

    for d in DEFAULT_IGNORED_DIRS:
        cmd.extend(["-g", f"!{d}/**"])

    cmd.extend(["-e", query, str(target_path)])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None

    # Exit code 0 = matches found, 1 = no matches found, >1 = error
    if proc.returncode not in (0, 1):
        # Ripgrep error (e.g. invalid regex syntax)
        # If regex syntax error, report error directly
        stderr_text = proc.stderr.strip()
        if "regex parse error" in stderr_text.lower() or "error: " in stderr_text.lower():
            return {
                "status": "error",
                "error": f"Ripgrep search error: {stderr_text}",
                "matches": [],
                "total_matches": 0,
                "truncated": False,
                "engine": "ripgrep",
            }
        # Otherwise fallback to Python engine
        return None

    matches: List[Dict[str, Any]] = []
    truncated = False

    for line in proc.stdout.splitlines():
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        if entry.get("type") == "match":
            data = entry.get("data", {})
            file_raw = data.get("path", {}).get("text", "")
            try:
                rel_file = str(Path(file_raw).relative_to(Path.cwd()))
            except (ValueError, OSError):
                rel_file = file_raw

            line_num = data.get("line_number", 0)
            submatches = data.get("submatches", [])
            col = submatches[0].get("start", 0) + 1 if submatches else None

            raw_text = data.get("lines", {}).get("text", "").rstrip("\r\n")
            content, is_trunc = _truncate_line(raw_text, max_line_length)

            matches.append(
                SearchMatch(
                    file=rel_file,
                    line_number=line_num,
                    column=col,
                    content=content,
                    truncated=is_trunc,
                ).to_dict()
            )

            if len(matches) >= max_results:
                truncated = True
                break

    return {
        "status": "success",
        "matches": matches,
        "total_matches": len(matches),
        "truncated": truncated,
        "engine": "ripgrep",
    }


def _matches_filters(
    path: Path,
    include_patterns: Optional[List[str]],
    exclude_patterns: Optional[List[str]],
) -> bool:
    """Check if file path passes include/exclude glob patterns."""
    name = path.name
    path_str = str(path)

    if include_patterns:
        if not any(fnmatch(name, pat) or fnmatch(path_str, pat) for pat in include_patterns):
            return False

    if exclude_patterns:
        if any(fnmatch(name, pat) or fnmatch(path_str, pat) for pat in exclude_patterns):
            return False

    return True


def _search_python(
    query: str,
    target_path: Path,
    regex: bool,
    case_sensitive: bool,
    max_results: int,
    max_line_length: int,
    timeout_seconds: float,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Execute search using pure Python regex line-streaming scanner."""
    flags = re.MULTILINE
    if not case_sensitive:
        flags |= re.IGNORECASE

    try:
        if regex:
            pattern = re.compile(query, flags)
        else:
            pattern = re.compile(re.escape(query), flags)
    except re.error as e:
        return {
            "status": "error",
            "error": f"Invalid regex pattern: {e}",
            "matches": [],
            "total_matches": 0,
            "truncated": False,
            "engine": "python_regex",
        }

    matches: List[Dict[str, Any]] = []
    truncated = False
    start_time = time.monotonic()

    # Determine files to scan
    files_to_scan: List[Path] = []
    if target_path.is_file():
        files_to_scan = [target_path]
    elif target_path.is_dir():
        for root, dirs, files in os.walk(target_path):
            # Prune ignored directories in-place
            dirs[:] = [d for d in dirs if d not in DEFAULT_IGNORED_DIRS and not d.startswith(".")]

            for file_name in files:
                p = Path(root) / file_name
                if p.suffix.lower() in DEFAULT_IGNORED_EXTS:
                    continue
                if not _matches_filters(p, include_patterns, exclude_patterns):
                    continue
                files_to_scan.append(p)
    else:
        return {
            "status": "error",
            "error": f"Target path does not exist: {target_path}",
            "matches": [],
            "total_matches": 0,
            "truncated": False,
            "engine": "python_regex",
        }

    for file_path in files_to_scan:
        if time.monotonic() - start_time > timeout_seconds:
            truncated = True
            break

        try:
            if file_path.stat().st_size > MAX_FILE_SIZE_BYTES:
                continue
            if _is_binary(file_path):
                continue
        except OSError:
            continue

        try:
            rel_file = str(file_path.relative_to(Path.cwd()))
        except (ValueError, OSError):
            rel_file = str(file_path)

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for line_num, raw_line in enumerate(f, start=1):
                    line = raw_line.rstrip("\r\n")
                    m = pattern.search(line)
                    if m:
                        col = m.start() + 1
                        content, is_trunc = _truncate_line(line, max_line_length)
                        matches.append(
                            SearchMatch(
                                file=rel_file,
                                line_number=line_num,
                                column=col,
                                content=content,
                                truncated=is_trunc,
                            ).to_dict()
                        )

                        if len(matches) >= max_results:
                            truncated = True
                            break
        except (OSError, UnicodeDecodeError):
            continue

        if len(matches) >= max_results:
            truncated = True
            break

    return {
        "status": "success",
        "matches": matches,
        "total_matches": len(matches),
        "truncated": truncated,
        "engine": "python_regex",
    }


def search_code(
    query: str,
    path: str = ".",
    regex: bool = False,
    case_sensitive: bool = False,
    max_results: int = 50,
    max_line_length: int = 200,
    timeout_seconds: float = 10.0,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Search code across files using ripgrep where available, with Python regex fallback.

    Args:
        query: String or regex pattern to search for.
        path: Path to directory or file to search.
        regex: If True, treat query as regex; if False, literal string match.
        case_sensitive: If True, perform case-sensitive search.
        max_results: Maximum total matches to return (1-1000).
        max_line_length: Maximum length of matched content line before truncation.
        timeout_seconds: Maximum time allowed for search before returning results.
        include_patterns: Optional list of glob patterns to include (e.g. ['*.py']).
        exclude_patterns: Optional list of glob patterns to exclude.

    Returns:
        Dict containing status, query, path, matches, total_matches, truncated, engine, duration_ms.
    """
    start_time = time.monotonic()
    bounded_max_results = max(1, min(max_results, 1000))
    bounded_line_length = max(20, min(max_line_length, 2000))

    if not query:
        return {
            "status": "success",
            "query": "",
            "path": path,
            "regex": regex,
            "case_sensitive": case_sensitive,
            "total_matches": 0,
            "truncated": False,
            "engine": "none",
            "matches": [],
            "duration_ms": 0.0,
        }

    target = Path(path).resolve()
    if not target.exists():
        return {
            "status": "error",
            "error": f"Path does not exist: {path}",
            "query": query,
            "path": path,
            "regex": regex,
            "case_sensitive": case_sensitive,
            "total_matches": 0,
            "truncated": False,
            "engine": "none",
            "matches": [],
            "duration_ms": round((time.monotonic() - start_time) * 1000, 2),
        }

    # Attempt Engine A: ripgrep
    res = _search_ripgrep(
        query=query,
        target_path=target,
        regex=regex,
        case_sensitive=case_sensitive,
        max_results=bounded_max_results,
        max_line_length=bounded_line_length,
        timeout_seconds=timeout_seconds,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
    )

    # Fallback to Engine B: Python regex scanner
    if res is None:
        res = _search_python(
            query=query,
            target_path=target,
            regex=regex,
            case_sensitive=case_sensitive,
            max_results=bounded_max_results,
            max_line_length=bounded_line_length,
            timeout_seconds=timeout_seconds,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
        )

    duration_ms = round((time.monotonic() - start_time) * 1000, 2)
    res["query"] = query
    res["path"] = str(path)
    res["regex"] = regex
    res["case_sensitive"] = case_sensitive
    res["duration_ms"] = duration_ms

    return res


async def search_code_async(
    query: str,
    path: str = ".",
    regex: bool = False,
    case_sensitive: bool = False,
    max_results: int = 50,
    max_line_length: int = 200,
    timeout_seconds: float = 10.0,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Asynchronous search wrapper for non-blocking FastAPI and MCP executions."""
    return await asyncio.to_thread(
        search_code,
        query=query,
        path=path,
        regex=regex,
        case_sensitive=case_sensitive,
        max_results=max_results,
        max_line_length=max_line_length,
        timeout_seconds=timeout_seconds,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
    )
