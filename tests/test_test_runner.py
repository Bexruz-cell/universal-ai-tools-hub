"""Unit tests for src/coding_tools/test_runner.py."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import pytest

from src.coding_tools.test_runner import (
    CompileError,
    TestFailureDetail,
    TestRunResult,
    TestStatus,
    VerificationResult,
    _parse_pytest_output,
    compile_files,
    resolve_test_targets,
    run_targeted_tests,
    truncate_output,
    verify_changes,
)


def test_truncate_output_untruncated():
    short_text = "Line 1\nLine 2\nLine 3"
    bounded, was_truncated = truncate_output(short_text, max_bytes=1000, max_lines=10)
    assert not was_truncated
    assert bounded == short_text


def test_truncate_output_by_lines():
    lines = [f"Log entry {i}" for i in range(100)]
    long_text = "\n".join(lines)
    bounded, was_truncated = truncate_output(long_text, max_lines=20, max_bytes=50_000)
    assert was_truncated
    assert "TRUNCATED" in bounded
    assert "Log entry 0" in bounded  # Head preserved
    assert "Log entry 99" in bounded  # Tail preserved


def test_truncate_output_by_bytes():
    heavy_line = "A" * 1000
    long_text = "\n".join([heavy_line for _ in range(50)])
    bounded, was_truncated = truncate_output(long_text, max_bytes=5000, max_lines=200)
    assert was_truncated
    assert len(bounded.encode("utf-8")) <= 5500
    assert "TRUNCATED" in bounded


def test_compile_files_valid(tmp_path):
    valid_py = tmp_path / "valid.py"
    valid_py.write_text("def hello() -> str:\n    return 'world'\n", encoding="utf-8")
    errors = compile_files([valid_py])
    assert len(errors) == 0


def test_compile_files_syntax_error(tmp_path):
    bad_py = tmp_path / "broken.py"
    bad_py.write_text("def broken(:\n    pass\n", encoding="utf-8")
    errors = compile_files([bad_py])
    assert len(errors) == 1
    err = errors[0]
    assert err.line_number == 1
    assert "broken.py" in err.file_path
    assert "invalid syntax" in err.error_message.lower() or "syntax" in err.error_message.lower()
    assert err.text_line == "def broken(:"
    assert isinstance(err.to_dict(), dict)


def test_compile_files_ignores_non_py(tmp_path):
    txt_file = tmp_path / "note.txt"
    txt_file.write_text("not a python file", encoding="utf-8")
    errors = compile_files([txt_file])
    assert len(errors) == 0


def test_resolve_test_targets_direct():
    test_file = "tests/test_tools.py"
    resolved = resolve_test_targets([test_file])
    assert any("test_tools.py" in target for target in resolved)


def test_resolve_test_targets_mapping():
    source_file = "src/core/tools.py"
    resolved = resolve_test_targets([source_file])
    assert any("test_tools.py" in target for target in resolved)


def test_parse_pytest_output():
    sample_stdout = """
============================= test session starts =============================
tests/test_foo.py .F.
=================================== FAILURES ===================================
__________________________________ test_fail ___________________________________
    def test_fail():
>       assert 1 == 2
E       assert 1 == 2
=========================== short test summary info ===========================
FAILED tests/test_foo.py::test_fail - assert 1 == 2
=================== 1 failed, 2 passed, 1 warning in 0.45s ====================
"""
    parsed = _parse_pytest_output(sample_stdout, "", 1)
    stats = parsed["stats"]
    assert stats["passed"] == 2
    assert stats["failed"] == 1
    assert parsed["total"] == 3
    assert len(parsed["failures"]) >= 1
    assert any("test_foo.py::test_fail" in f.node_id for f in parsed["failures"])


def test_run_targeted_tests_success():
    res = run_targeted_tests(targets=["tests/test_tools.py"], timeout_seconds=30.0)
    assert res.success is True
    assert res.status == TestStatus.PASSED
    assert res.exit_code == 0
    assert res.passed > 0
    assert res.failed == 0
    assert not res.timed_out
    assert isinstance(res.to_dict(), dict)


def test_run_targeted_tests_timeout(tmp_path):
    slow_test = tmp_path / "test_slow_runner.py"
    slow_test.write_text("import time\ndef test_sleep():\n    time.sleep(5)\n", encoding="utf-8")
    res = run_targeted_tests(targets=[str(slow_test)], timeout_seconds=1.0)
    assert res.timed_out is True
    assert res.status == TestStatus.TIMEOUT
    assert res.success is False


def test_verify_changes_gate1_failure(tmp_path):
    bad_code = tmp_path / "bad_syntax.py"
    bad_code.write_text("class Unfinished{\n", encoding="utf-8")
    result = verify_changes(changed_files=[bad_code])
    assert result.passed is False
    assert result.compile_success is False
    assert len(result.compile_errors) == 1
    assert result.test_result is None
    assert "Gate 1 (py_compile)" in result.summary


def test_verify_changes_gate2_success():
    result = verify_changes(
        changed_files=["src/core/tools.py"],
        test_targets=["tests/test_tools.py"],
        timeout_seconds=30.0,
    )
    assert result.passed is True
    assert result.compile_success is True
    assert len(result.compile_errors) == 0
    assert result.test_result is not None
    assert result.test_result.success is True
    assert "Verification PASSED" in result.summary
    assert isinstance(result.to_dict(), dict)
