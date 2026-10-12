"""Test Runner: Isolated, Timeout-Guarded Test Execution & Verification Gate.

Provides surgical targeted pytest execution, output buffering with token hygiene,
in-memory bytecode compilation (py_compile), process isolation, and automated
regression verification for autonomous agent workflows.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import os
from pathlib import Path
import py_compile
import re
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


class TestStatus(str, Enum):
    """Execution status for a test run."""
    __test__ = False
    PASSED = "passed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ERROR = "error"
    SKIPPED = "skipped"
    NO_TESTS = "no_tests"


@dataclass
class TestFailureDetail:
    """Detailed breakdown of a failed test case."""
    __test__ = False
    node_id: str
    error_message: str
    traceback_snippet: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TestRunResult:
    """Structured result of a pytest execution."""
    __test__ = False
    success: bool
    status: TestStatus
    exit_code: int
    duration_seconds: float
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    failures: List[TestFailureDetail] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    truncated: bool = False
    timed_out: bool = False
    command: List[str] = field(default_factory=list)
    cwd: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


@dataclass
class CompileError:
    """Syntax or compilation error returned by py_compile."""
    file_path: str
    line_number: Optional[int] = None
    offset: Optional[int] = None
    error_message: str = ""
    text_line: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VerificationResult:
    """Result of the complete multi-stage verification gate."""
    passed: bool
    compile_success: bool
    compile_errors: List[CompileError] = field(default_factory=list)
    test_result: Optional[TestRunResult] = None
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "compile_success": self.compile_success,
            "compile_errors": [err.to_dict() for err in self.compile_errors],
            "test_result": self.test_result.to_dict() if self.test_result else None,
            "summary": self.summary,
        }


def truncate_output(
    text: str,
    max_bytes: int = 32_000,
    max_lines: int = 150,
    head_ratio: float = 0.3,
) -> Tuple[str, bool]:
    """Truncates output to enforce context window hygiene while preserving head & tail.

    Args:
        text: Raw output string to truncate.
        max_bytes: Maximum allowed size in bytes (UTF-8).
        max_lines: Maximum allowed line count.
        head_ratio: Proportion of allowed lines allocated to the head (rest to tail).

    Returns:
        Tuple of (bounded_text, was_truncated).
    """
    if not text:
        return "", False

    encoded = text.encode("utf-8", errors="replace")
    lines = text.splitlines(keepends=True)

    if len(encoded) <= max_bytes and len(lines) <= max_lines:
        return text, False

    total_lines = len(lines)
    head_count = max(1, int(max_lines * head_ratio))
    tail_count = max(1, max_lines - head_count)

    if total_lines <= head_count + tail_count:
        # Lines are few but bytes are large; truncate characters in the middle
        mid_byte = max_bytes // 2
        head_bytes = encoded[:mid_byte].decode("utf-8", errors="ignore")
        tail_bytes = encoded[-mid_byte:].decode("utf-8", errors="ignore")
        truncated_size = len(encoded) - (len(head_bytes.encode()) + len(tail_bytes.encode()))
        marker = (
            f"\n... [TRUNCATED {truncated_size} bytes for token efficiency] ...\n"
        )
        return head_bytes + marker + tail_bytes, True

    head_part = "".join(lines[:head_count])
    tail_part = "".join(lines[-tail_count:])
    omitted_lines = total_lines - (head_count + tail_count)
    omitted_bytes = len(encoded) - (len(head_part.encode()) + len(tail_part.encode()))

    marker = (
        f"\n... [TRUNCATED {omitted_lines} lines / {omitted_bytes} bytes for token efficiency] ...\n"
    )
    bounded_text = head_part + marker + tail_part

    # Ensure byte bound is strictly respected even after line truncation
    if len(bounded_text.encode("utf-8", errors="replace")) > max_bytes:
        half_bytes = (max_bytes - len(marker.encode("utf-8"))) // 2
        safe_head = head_part.encode("utf-8")[:max(0, half_bytes)].decode("utf-8", errors="ignore")
        safe_tail = tail_part.encode("utf-8")[-max(0, half_bytes):].decode("utf-8", errors="ignore")
        bounded_text = safe_head + marker + safe_tail

    return bounded_text, True


def _kill_process_tree(proc: subprocess.Popen) -> None:
    """Terminates a process and all its child processes cleanly across platforms."""
    pid = proc.pid
    if os.name == "nt":
        try:
            # Force kill entire process tree on Windows
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        except Exception:
            pass

    try:
        proc.kill()
    except Exception:
        pass

    try:
        proc.wait(timeout=2)
    except Exception:
        pass


def _parse_pytest_output(stdout: str, stderr: str, exit_code: int) -> Dict[str, Any]:
    """Parses pytest terminal output into structured test statistics and failures."""
    combined = f"{stdout}\n{stderr}"
    stats: Dict[str, int] = {
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
    }

    # Extract test counts from pytest summary line (e.g., '1 failed, 84 passed, 1 warning in 12.78s')
    for line in reversed(combined.splitlines()):
        line_clean = line.strip()
        if re.search(r"in\s+[\d\.]+s", line_clean) and ("passed" in line_clean or "failed" in line_clean or "error" in line_clean):
            matches = re.findall(
                r"(\d+)\s+(passed|failed|skipped|xfailed|xpassed|error|errors)",
                line_clean,
                re.IGNORECASE,
            )
            for count_str, category in matches:
                category_lower = category.lower()
                count = int(count_str)
                if category_lower in ("passed", "xpassed"):
                    stats["passed"] += count
                elif category_lower in ("failed", "xfailed"):
                    stats["failed"] += count
                elif category_lower == "skipped":
                    stats["skipped"] += count
                elif category_lower in ("error", "errors"):
                    stats["errors"] += count
            break

    # Extract failure details from 'short test summary info' or 'FAILED ...' lines
    failures: List[TestFailureDetail] = []
    seen_nodes: set[str] = set()

    # Pattern 1: 'FAILED tests/foo.py::test_bar - AssertionError: ...'
    failed_pattern = re.compile(
        r"^FAILED\s+([^\s:]+(?:::[^\s]+)?)(?:\s*-\s*(.*))?$",
        re.MULTILINE,
    )
    for match in failed_pattern.finditer(combined):
        node_id = match.group(1).strip()
        reason = (match.group(2) or "").strip()
        if node_id and node_id not in seen_nodes:
            seen_nodes.add(node_id)
            failures.append(TestFailureDetail(node_id=node_id, error_message=reason))

    # Pattern 2: Section headers '____ test_name ____'
    section_pattern = re.compile(r"_{4,}\s+([^\n_]+)\s+_{4,}")
    for match in section_pattern.finditer(combined):
        node_name = match.group(1).strip()
        if node_name and node_name not in seen_nodes:
            seen_nodes.add(node_name)
            failures.append(TestFailureDetail(node_id=node_name, error_message="Test failure"))

    total = stats["passed"] + stats["failed"] + stats["skipped"] + stats["errors"]

    return {
        "stats": stats,
        "total": total,
        "failures": failures,
    }


def compile_files(
    files: Sequence[Union[Path, str]],
    doraise: bool = False,
) -> List[CompileError]:
    """Compiles Python files in-memory to validate syntax and bytecode without execution.

    Args:
        files: List or sequence of file paths to check.
        doraise: If True, raises PyCompileError on the first error.

    Returns:
        List of CompileError objects (empty if all files passed compilation).
    """
    errors: List[CompileError] = []

    for file_entry in files:
        file_path = Path(file_entry).resolve()
        if not file_path.exists() or file_path.suffix != ".py":
            continue

        try:
            py_compile.compile(str(file_path), doraise=True)
        except py_compile.PyCompileError as exc:
            if doraise:
                raise

            line_no = None
            offset = None
            text_line = None
            msg = str(exc)

            # Inspect underlying SyntaxError if available in exception arguments
            if len(exc.args) > 2 and isinstance(exc.args[2], SyntaxError):
                syn_err: SyntaxError = exc.args[2]
                line_no = syn_err.lineno
                offset = syn_err.offset
                text_line = syn_err.text.strip() if syn_err.text else None
                msg = syn_err.msg or msg

            errors.append(
                CompileError(
                    file_path=str(file_path),
                    line_number=line_no,
                    offset=offset,
                    error_message=msg,
                    text_line=text_line,
                )
            )

    return errors


def resolve_test_targets(
    changed_files: Sequence[Union[Path, str]],
    test_dir: Union[Path, str] = "tests",
    workspace_root: Optional[Union[Path, str]] = None,
) -> List[str]:
    """Maps changed source files to candidate pytest test files using heuristic matching.

    Args:
        changed_files: List of modified source files.
        test_dir: Test directory relative to workspace root (defaults to 'tests').
        workspace_root: Project root directory (defaults to cwd).

    Returns:
        List of test target file paths as strings.
    """
    root = Path(workspace_root or Path.cwd()).resolve()
    tests_path = (root / test_dir).resolve() if not Path(test_dir).is_absolute() else Path(test_dir).resolve()

    resolved_targets: set[str] = set()

    for item in changed_files:
        p = Path(item).resolve()

        # If the file itself is already inside tests/ and is a test file
        if p.name.startswith("test_") or p.name.endswith("_test.py"):
            try:
                rel = p.relative_to(root)
                resolved_targets.add(str(rel))
            except ValueError:
                resolved_targets.add(str(p))
            continue

        if p.suffix != ".py":
            continue

        stem = p.stem  # e.g., 'path_guard', 'api_adapter', 'tools'

        # Candidate names
        candidates = [
            f"test_{stem}.py",
            f"{stem}_test.py",
            f"test_{stem.replace('_', '')}.py",
        ]

        # Also search in subdirectories matching module hierarchy
        matched = False
        if tests_path.exists():
            for cand in candidates:
                # Direct match in test root
                candidate_path = tests_path / cand
                if candidate_path.exists():
                    try:
                        resolved_targets.add(str(candidate_path.relative_to(root)))
                    except ValueError:
                        resolved_targets.add(str(candidate_path))
                    matched = True

                # Search nested test folders
                for match in tests_path.rglob(cand):
                    try:
                        resolved_targets.add(str(match.relative_to(root)))
                    except ValueError:
                        resolved_targets.add(str(match))
                    matched = True

        # Heuristic prefix search if no exact match (e.g. test_api.py for api_adapter.py)
        if not matched and tests_path.exists():
            parts = stem.split("_")
            if parts:
                first_part = parts[0]
                prefix_cand = tests_path / f"test_{first_part}.py"
                if prefix_cand.exists():
                    try:
                        resolved_targets.add(str(prefix_cand.relative_to(root)))
                    except ValueError:
                        resolved_targets.add(str(prefix_cand))

    return sorted(list(resolved_targets))


def run_targeted_tests(
    targets: Optional[Sequence[str]] = None,
    cwd: Optional[Union[Path, str]] = None,
    timeout_seconds: float = 60.0,
    max_output_bytes: int = 32_000,
    max_output_lines: int = 150,
    pytest_args: Optional[Sequence[str]] = None,
    env_overrides: Optional[Dict[str, str]] = None,
    isolated_env: bool = True,
    python_executable: Optional[str] = None,
) -> TestRunResult:
    """Executes pytest targets with process timeouts, bounded buffers, and isolated environments.

    Args:
        targets: Specific pytest targets (files, directories, or node IDs like tests/test_x.py::test_func).
        cwd: Working directory for pytest execution (defaults to current directory).
        timeout_seconds: Execution timeout before hard-kill.
        max_output_bytes: Maximum size for captured stdout and stderr.
        max_output_lines: Maximum line count for captured output.
        pytest_args: Additional pytest CLI arguments (default: ['-q']).
        env_overrides: Extra environment variables to inject.
        isolated_env: If True, sets up isolated environment variables (PYTHONUNBUFFERED, etc.).
        python_executable: Path to python interpreter (defaults to sys.executable).

    Returns:
        Structured TestRunResult containing execution metrics, status, and bounded logs.
    """
    exec_cwd = Path(cwd or Path.cwd()).resolve()
    py_exec = python_executable or sys.executable

    # Build command
    cmd: List[str] = [py_exec, "-m", "pytest"]
    if pytest_args:
        cmd.extend(pytest_args)
    else:
        cmd.append("-q")

    if targets:
        cmd.extend(targets)
    else:
        # Default to standard test directory
        cmd.append("tests")

    # Prepare environment
    env = os.environ.copy()
    if isolated_env:
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        # Ensure working directory is accessible on PYTHONPATH
        curr_py_path = env.get("PYTHONPATH", "")
        cwd_str = str(exec_cwd)
        if cwd_str not in curr_py_path.split(os.pathsep):
            env["PYTHONPATH"] = f"{cwd_str}{os.pathsep}{curr_py_path}" if curr_py_path else cwd_str

    if env_overrides:
        env.update(env_overrides)

    start_time = time.perf_counter()
    stdout_raw = ""
    stderr_raw = ""
    exit_code = -1
    timed_out = False

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(exec_cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )

        try:
            stdout_raw, stderr_raw = proc.communicate(timeout=timeout_seconds)
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_process_tree(proc)
            try:
                stdout_raw, stderr_raw = proc.communicate(timeout=2)
            except Exception:
                stdout_raw = stdout_raw or ""
                stderr_raw = stderr_raw or "Process timed out and was killed."
            exit_code = -9
    except Exception as exc:
        stderr_raw = f"Failed to spawn test runner process: {exc}"
        exit_code = -1

    duration = time.perf_counter() - start_time

    # Bounded buffer processing
    bounded_stdout, trunc_out = truncate_output(stdout_raw, max_bytes=max_output_bytes, max_lines=max_output_lines)
    bounded_stderr, trunc_err = truncate_output(stderr_raw, max_bytes=max_output_bytes, max_lines=max_output_lines)
    was_truncated = trunc_out or trunc_err

    # Parse pytest output
    parsed = _parse_pytest_output(stdout_raw, stderr_raw, exit_code)
    stats = parsed["stats"]
    failures = parsed["failures"]
    total = parsed["total"]

    # Determine status
    if timed_out:
        status = TestStatus.TIMEOUT
        success = False
    elif exit_code == 0:
        status = TestStatus.PASSED
        success = True
    elif exit_code == 5:
        status = TestStatus.NO_TESTS
        success = True  # No tests collected is not a regression failure
    elif stats["failed"] > 0 or stats["errors"] > 0 or exit_code == 1:
        status = TestStatus.FAILED
        success = False
    else:
        status = TestStatus.ERROR
        success = False

    return TestRunResult(
        success=success,
        status=status,
        exit_code=exit_code,
        duration_seconds=round(duration, 3),
        total=total,
        passed=stats["passed"],
        failed=stats["failed"],
        skipped=stats["skipped"],
        errors=stats["errors"],
        failures=failures,
        stdout=bounded_stdout,
        stderr=bounded_stderr,
        truncated=was_truncated,
        timed_out=timed_out,
        command=cmd,
        cwd=str(exec_cwd),
    )


def verify_changes(
    changed_files: Sequence[Union[Path, str]],
    test_targets: Optional[Sequence[str]] = None,
    cwd: Optional[Union[Path, str]] = None,
    timeout_seconds: float = 60.0,
    run_regression: bool = True,
    max_output_bytes: int = 32_000,
    max_output_lines: int = 150,
    python_executable: Optional[str] = None,
) -> VerificationResult:
    """Runs the complete verification gate: syntax validation, target tests, and regression.

    Args:
        changed_files: Sequence of modified files to verify.
        test_targets: Specific test targets. If None, auto-resolved from changed_files.
        cwd: Workspace working directory.
        timeout_seconds: Timeout per pytest invocation.
        run_regression: If True and no specific tests found, runs full regression suite.
        max_output_bytes: Output buffer limit.
        max_output_lines: Output line limit.
        python_executable: Python interpreter path.

    Returns:
        VerificationResult with compile status, test status, and diagnostic summary.
    """
    exec_cwd = Path(cwd or Path.cwd()).resolve()

    # Stage 1: Syntax & Bytecode Compilation Gate
    compile_errs = compile_files(changed_files)
    if compile_errs:
        summary_msg = (
            f"Verification FAILED at Gate 1 (py_compile): {len(compile_errs)} syntax/compilation error(s) found."
        )
        return VerificationResult(
            passed=False,
            compile_success=False,
            compile_errors=compile_errs,
            test_result=None,
            summary=summary_msg,
        )

    # Stage 2: Target Test Resolution
    targets_to_run: List[str] = []
    if test_targets:
        targets_to_run = list(test_targets)
    else:
        targets_to_run = resolve_test_targets(
            changed_files,
            test_dir="tests",
            workspace_root=exec_cwd,
        )
        if not targets_to_run and run_regression:
            targets_to_run = ["tests"]

    # Stage 3: Test Execution Gate
    test_res = run_targeted_tests(
        targets=targets_to_run,
        cwd=exec_cwd,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        max_output_lines=max_output_lines,
        python_executable=python_executable,
    )

    if test_res.success:
        summary_msg = (
            f"Verification PASSED: {test_res.passed} test(s) passed "
            f"(duration: {test_res.duration_seconds:.2f}s, exit code: {test_res.exit_code})."
        )
    else:
        summary_msg = (
            f"Verification FAILED at Gate 2 (pytest): {test_res.failed} failed, {test_res.errors} error(s) "
            f"(status: {test_res.status.value}, exit code: {test_res.exit_code})."
        )

    return VerificationResult(
        passed=test_res.success,
        compile_success=True,
        compile_errors=[],
        test_result=test_res,
        summary=summary_msg,
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Autonomous Test Runner & Verification Gate")
    parser.add_argument("files", nargs="*", help="Changed source files to verify")
    parser.add_argument("--test", nargs="*", help="Specific pytest targets")
    parser.add_argument("--timeout", type=float, default=60.0, help="Test timeout in seconds")
    parser.add_argument("--no-regression", action="store_true", help="Do not run full test suite if no targets matched")
    args = parser.parse_args()

    if args.files:
        res = verify_changes(
            changed_files=args.files,
            test_targets=args.test,
            timeout_seconds=args.timeout,
            run_regression=not args.no_regression,
        )
        print(f"Status: {'PASSED' if res.passed else 'FAILED'}")
        print(f"Summary: {res.summary}")
        if not res.compile_success:
            for ce in res.compile_errors:
                print(f"Compile Error: {ce.file_path}:{ce.line_number} - {ce.error_message}")
        sys.exit(0 if res.passed else 1)
    else:
        run_res = run_targeted_tests(targets=args.test, timeout_seconds=args.timeout)
        print(f"Status: {run_res.status.value}")
        print(f"Passed: {run_res.passed}, Failed: {run_res.failed}, Skipped: {run_res.skipped}")
        sys.exit(run_res.exit_code)
