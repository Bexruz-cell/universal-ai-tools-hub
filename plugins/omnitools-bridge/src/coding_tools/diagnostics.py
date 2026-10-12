"""OmniTools Universal AI Bridge - Stacktrace & Failure Diagnostician

Parses Python tracebacks, compiler stderr, pytest failure outputs,
pinpoints failing file and line, extracts surrounding source code, and suggests surgical fixes.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FrameInfo(BaseModel):
    file_path: str
    line_number: int
    function_name: str
    code_line: str = ""


class DiagnosticResult(BaseModel):
    error_type: str
    error_message: str
    failing_file: Optional[str] = None
    failing_line: Optional[int] = None
    failing_function: Optional[str] = None
    snippet: Optional[str] = None
    stack_frames: List[FrameInfo] = Field(default_factory=list)
    suggested_fix: Optional[str] = None
    category: str = "general_error"


def parse_traceback(traceback_text: str) -> DiagnosticResult:
    """Parse python traceback or compiler error string into structured diagnostic."""
    lines = traceback_text.strip().splitlines()
    frames: List[FrameInfo] = []
    
    # Regex to match traceback frame: File "...", line 123, in func_name
    frame_pattern = re.compile(r'File\s+"([^"]+)",\s+line\s+(\d+)(?:,\s+in\s+([^\n\r]+))?')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        match = frame_pattern.search(line)
        if match:
            fpath, lno_str, func = match.group(1), match.group(2), match.group(3) or "<module>"
            code_line = ""
            if i + 1 < len(lines) and not lines[i + 1].strip().startswith("File "):
                code_line = lines[i + 1].strip()
                i += 1
            frames.append(FrameInfo(
                file_path=fpath,
                line_number=int(lno_str),
                function_name=func,
                code_line=code_line,
            ))
        i += 1

    # Extract last line as ErrorType: ErrorMessage
    error_type = "UnknownError"
    error_msg = ""
    for line in reversed(lines):
        line_clean = line.strip()
        if line_clean and not line_clean.startswith("File ") and not line_clean.startswith("Traceback"):
            parts = line_clean.split(":", 1)
            if len(parts) == 2 and ("Error" in parts[0] or "Exception" in parts[0]):
                error_type = parts[0].strip()
                error_msg = parts[1].strip()
                break
            elif not error_msg:
                error_msg = line_clean

    failing_file: Optional[str] = None
    failing_line: Optional[int] = None
    failing_func: Optional[str] = None
    snippet: Optional[str] = None

    if frames:
        last_frame = frames[-1]
        failing_file = last_frame.file_path
        failing_line = last_frame.line_number
        failing_func = last_frame.function_name

        # Extract code snippet if file exists
        p = Path(failing_file)
        if p.is_file():
            try:
                content_lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
                start = max(0, failing_line - 3)
                end = min(len(content_lines), failing_line + 2)
                numbered = []
                for idx in range(start, end):
                    marker = " ->" if (idx + 1) == failing_line else "   "
                    numbered.append(f"{idx + 1:4d}{marker} {content_lines[idx]}")
                snippet = "\n".join(numbered)
            except Exception:
                pass

    # Category and suggestion heuristics
    category = "runtime_exception"
    suggestion = "Inspect variable values and check for None or invalid inputs."
    if "SyntaxError" in error_type:
        category = "syntax_error"
        suggestion = "Check for missing parenthesis, unmatched quotes, or invalid indentation."
    elif "ImportError" in error_type or "ModuleNotFoundError" in error_type:
        category = "import_error"
        suggestion = "Verify module name in requirements.txt or check relative import level."
    elif "AssertionError" in error_type:
        category = "test_failure"
        suggestion = "Check actual vs expected test output or mocked responses."
    elif "AttributeError" in error_type:
        category = "attribute_error"
        suggestion = "Ensure object is initialized and has the referenced attribute before access."
    elif "KeyError" in error_type:
        category = "key_error"
        suggestion = "Use .get() with a default value or verify dictionary keys."

    return DiagnosticResult(
        error_type=error_type,
        error_message=error_msg,
        failing_file=failing_file,
        failing_line=failing_line,
        failing_function=failing_func,
        snippet=snippet,
        stack_frames=frames,
        suggested_fix=suggestion,
        category=category,
    )


def diagnose_error(
    error_traceback: str,
    related_files: Optional[List[str]] = None,
    suggest_fix: bool = True,
) -> Dict[str, Any]:
    """MCP Tool #13 entry point: parse traceback and diagnose root cause."""
    res = parse_traceback(error_traceback)
    out = res.model_dump()
    if not suggest_fix:
        out.pop("suggested_fix", None)
    return out
