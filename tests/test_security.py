"""Comprehensive Security Test Suite

Tests PathGuard and CommandGuard for:
- Strict workspace boundary enforcement and path traversal defenses
- Symlink breakout rejection
- Null-byte injection and Windows DOS device defense
- Shell=True absolute prohibition
- Mandatory bounded timeout enforcement and process termination
- Subprocess isolation across sync, async, and popen interfaces
"""

import os
from pathlib import Path
import subprocess
import sys
import pytest

from src.security.path_guard import (
    PathGuard,
    SecurityError,
    PathTraversalError,
    DisallowedPathError,
)
from src.security.command_guard import (
    CommandGuard,
    CommandSecurityError,
    CommandExecutionTimeout,
)


# ==============================================================================
# 1. PathGuard Test Suite
# ==============================================================================

def test_path_guard_valid_contained_file(tmp_path: Path):
    guard = PathGuard(workspace_root=tmp_path)
    file_p = tmp_path / "subdir" / "test.txt"
    file_p.parent.mkdir(parents=True)
    file_p.write_text("secure content", encoding="utf-8")

    resolved = guard.validate_path(file_p, must_be_file=True)
    assert resolved == file_p.resolve()
    assert guard.is_safe_path(file_p)


def test_path_guard_blocks_parent_traversal(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside_file = tmp_path / "secret.txt"
    outside_file.write_text("secret", encoding="utf-8")

    guard = PathGuard(workspace_root=workspace)

    # Relative traversal
    with pytest.raises(PathTraversalError):
        guard.validate_path(Path("..") / "secret.txt")

    # Double traversal
    with pytest.raises(PathTraversalError):
        guard.validate_path(workspace / "sub" / ".." / ".." / "secret.txt")

    # Absolute outside target
    with pytest.raises(PathTraversalError):
        guard.validate_path(outside_file)

    assert not guard.is_safe_path(outside_file)


def test_path_guard_blocks_null_byte_injection(tmp_path: Path):
    guard = PathGuard(workspace_root=tmp_path)
    with pytest.raises(PathTraversalError, match="Null byte"):
        guard.validate_path("sub/file.txt\0evil.exe")


@pytest.mark.parametrize("reserved_name", [
    "CON", "PRN", "AUX", "NUL", "COM1", "COM9", "LPT1", "con.txt", "nul.json"
])
def test_path_guard_blocks_windows_reserved_device_names(tmp_path: Path, reserved_name: str):
    guard = PathGuard(workspace_root=tmp_path)
    with pytest.raises(DisallowedPathError, match="Windows reserved device"):
        guard.validate_path(reserved_name)


def test_path_guard_blocks_alternate_data_streams(tmp_path: Path):
    guard = PathGuard(workspace_root=tmp_path)
    with pytest.raises(DisallowedPathError, match="Alternate Data Stream"):
        guard.validate_path(tmp_path / "file.txt:hidden_stream")


def test_path_guard_file_and_directory_types(tmp_path: Path):
    guard = PathGuard(workspace_root=tmp_path)
    test_dir = tmp_path / "folder"
    test_dir.mkdir()
    test_file = tmp_path / "regular.txt"
    test_file.write_text("content", encoding="utf-8")

    # must_be_file on dir
    with pytest.raises(DisallowedPathError, match="not a file"):
        guard.validate_path(test_dir, must_be_file=True)

    # must_be_dir on file
    with pytest.raises(DisallowedPathError, match="not a directory"):
        guard.validate_path(test_file, must_be_dir=True)


def test_path_guard_nonexistent_paths(tmp_path: Path):
    guard = PathGuard(workspace_root=tmp_path)
    missing = tmp_path / "new_dir" / "new_file.txt"

    # Not allowed by default
    with pytest.raises(FileNotFoundError):
        guard.validate_path(missing, allow_nonexistent=False)

    # Allowed when allow_nonexistent=True
    valid = guard.validate_path(missing, allow_nonexistent=True)
    assert valid == missing.resolve()

    # Traversal on nonexistent must still fail
    with pytest.raises(PathTraversalError):
        guard.validate_path(tmp_path / ".." / "nonexistent.txt", allow_nonexistent=True)


def test_path_guard_symlink_mock_escape(tmp_path: Path):
    from unittest.mock import patch
    workspace = tmp_path / "ws"
    workspace.mkdir()
    guard = PathGuard(workspace_root=workspace)

    mock_link = workspace / "fake_symlink.txt"
    mock_link.write_text("dummy", encoding="utf-8")

    outside_resolved = (tmp_path / "outside.txt").resolve()
    with patch.object(Path, "resolve", return_value=outside_resolved):
        with pytest.raises(PathTraversalError):
            guard.validate_path(mock_link)


def test_path_guard_symlink_boundary_defense(tmp_path: Path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside data", encoding="utf-8")

    link_to_outside = workspace / "escape_symlink.txt"
    try:
        os.symlink(outside, link_to_outside)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation not supported in current environment/permissions")

    guard = PathGuard(workspace_root=workspace)

    # Resolving symlink pointing outside must trigger PathTraversalError
    with pytest.raises(PathTraversalError):
        guard.validate_path(link_to_outside)


def test_path_guard_safe_file_operations(tmp_path: Path):
    guard = PathGuard(workspace_root=tmp_path)
    target = tmp_path / "data" / "note.txt"

    # Write text
    written = guard.safe_write_text(target, "hello secure world")
    assert written.exists()

    # Read text
    content = guard.safe_read_text(target)
    assert content == "hello secure world"

    # Binary write & read
    bin_target = tmp_path / "binary.bin"
    guard.safe_write_bytes(bin_target, b"\x01\x02\x03\x04")
    assert guard.safe_read_bytes(bin_target) == b"\x01\x02\x03\x04"


def test_path_guard_file_size_limits(tmp_path: Path):
    guard = PathGuard(workspace_root=tmp_path)
    big_file = tmp_path / "large.txt"
    big_file.write_text("A" * 1024, encoding="utf-8")

    with pytest.raises(SecurityError, match="exceeds safety limit"):
        guard.safe_read_text(big_file, max_bytes=512)

    with pytest.raises(SecurityError, match="exceeds safety limit"):
        guard.safe_read_bytes(big_file, max_bytes=512)


# ==============================================================================
# 2. CommandGuard Test Suite
# ==============================================================================

def test_command_guard_prohibits_shell_true():
    guard = CommandGuard()
    with pytest.raises(CommandSecurityError, match="shell=True is strictly prohibited"):
        guard.validate_command(["echo", "hi"], shell=True)

    with pytest.raises(CommandSecurityError, match="shell=True is strictly prohibited"):
        guard.safe_run(["echo", "hi"], shell=True)

    with pytest.raises(CommandSecurityError, match="shell=True is strictly prohibited"):
        guard.safe_popen(["echo", "hi"], shell=True)


def test_command_guard_prohibits_raw_strings():
    guard = CommandGuard()
    with pytest.raises(CommandSecurityError, match="sequence of strings"):
        guard.safe_run("python -c 'print(1)'")


def test_command_guard_rejects_empty_and_null_bytes():
    guard = CommandGuard()
    with pytest.raises(CommandSecurityError, match="cannot be empty"):
        guard.validate_command([])

    with pytest.raises(CommandSecurityError, match="Null byte detected"):
        guard.validate_command(["echo", "test\0injected"])

    with pytest.raises(CommandSecurityError, match="cannot be blank"):
        guard.validate_command(["   ", "arg"])


def test_command_guard_timeout_bounds():
    guard = CommandGuard(default_timeout=10.0, max_timeout=60.0)

    with pytest.raises(CommandSecurityError, match="strictly positive"):
        guard.validate_command(["echo", "hi"], timeout=0)

    with pytest.raises(CommandSecurityError, match="strictly positive"):
        guard.validate_command(["echo", "hi"], timeout=-10)

    with pytest.raises(CommandSecurityError, match="exceeds maximum allowed"):
        guard.validate_command(["echo", "hi"], timeout=100.0)


def test_command_guard_safe_run_success():
    guard = CommandGuard()
    res = guard.safe_run(
        [sys.executable, "-c", "import sys; print('cmd_guard_ok'); sys.stderr.write('err_ok\\n')"],
        timeout=10.0,
    )
    assert res.returncode == 0
    assert "cmd_guard_ok" in res.stdout
    assert "err_ok" in res.stderr


def test_command_guard_safe_run_timeout():
    guard = CommandGuard()
    with pytest.raises(CommandExecutionTimeout):
        guard.safe_run(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            timeout=0.3,
        )


def test_command_guard_cwd_boundary_enforcement(tmp_path: Path):
    ws = tmp_path / "guard_ws"
    ws.mkdir()
    guard = CommandGuard(path_guard=PathGuard(workspace_root=ws))

    # CWD within workspace is allowed
    sub = ws / "sub"
    sub.mkdir()
    res = guard.safe_run([sys.executable, "-c", "import os; print(os.getcwd())"], cwd=sub)
    assert res.returncode == 0
    assert str(sub.resolve()).lower() in res.stdout.strip().lower()

    # CWD outside workspace is rejected
    outside = tmp_path / "outside_dir"
    outside.mkdir()
    with pytest.raises(PathTraversalError):
        guard.safe_run([sys.executable, "-c", "print(1)"], cwd=outside)


@pytest.mark.asyncio
async def test_command_guard_safe_async_run():
    guard = CommandGuard()
    returncode, stdout, stderr = await guard.safe_async_run(
        [sys.executable, "-c", "print('async_guard_ok')"],
        timeout=10.0,
    )
    assert returncode == 0
    assert "async_guard_ok" in stdout


@pytest.mark.asyncio
async def test_command_guard_safe_async_run_timeout():
    guard = CommandGuard()
    with pytest.raises(CommandExecutionTimeout):
        await guard.safe_async_run(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            timeout=0.3,
        )


def test_command_guard_safe_popen():
    guard = CommandGuard()
    proc = guard.safe_popen(
        [sys.executable, "-c", "import sys; print(sys.stdin.read().upper())"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout, stderr = proc.communicate(input="test_popen_pipe\n", timeout=5)
    assert "TEST_POPEN_PIPE" in stdout
