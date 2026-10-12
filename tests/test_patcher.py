"""Tests for OmniTools Universal AI Hub - Safe Patch Engine (src/coding_tools/patcher.py)"""

import os
from pathlib import Path
import pytest
import shutil
import tempfile

from src.coding_tools.patcher import (
    ConfirmationRequiredError,
    PatchApplyResult,
    PatchProposalResult,
    WorkspaceSecurityError,
    apply_patch,
    clear_patch_cache,
    get_cached_proposal,
    propose_patch,
    validate_workspace_path,
    verify_syntax,
)


@pytest.fixture
def temp_workspace():
    """Create an isolated temporary workspace directory."""
    temp_dir = tempfile.mkdtemp(prefix="test_patcher_ws_")
    ws_path = Path(temp_dir).resolve()
    yield ws_path
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_propose_patch_is_strictly_read_only(temp_workspace):
    """Verify that propose_patch never modifies the file system or target file."""
    test_file = temp_workspace / "sample.py"
    initial_content = "def hello():\n    return 'hello'\n"
    test_file.write_text(initial_content, encoding="utf-8")
    mtime_before = test_file.stat().st_mtime_ns

    new_content = "def hello():\n    return 'world'\n"
    proposal = propose_patch(test_file, new_content=new_content, workspace_root=temp_workspace)

    assert isinstance(proposal, PatchProposalResult)
    assert proposal.can_apply_cleanly is True
    assert proposal.patch_id.startswith("patch-")
    assert "-    return 'hello'" in proposal.diff
    assert "+    return 'world'" in proposal.diff

    # Assert file on disk was NOT touched
    assert test_file.read_text(encoding="utf-8") == initial_content
    assert test_file.stat().st_mtime_ns == mtime_before

    # Verify cached retrieval
    cached = get_cached_proposal(proposal.patch_id)
    assert cached is not None
    assert cached.patch_id == proposal.patch_id


def test_workspace_security_boundary(temp_workspace):
    """Verify that paths outside workspace_root or traversing out are blocked."""
    outside_file = temp_workspace.parent / "escape.py"

    with pytest.raises(WorkspaceSecurityError):
        validate_workspace_path(outside_file, workspace_root=temp_workspace)

    with pytest.raises(WorkspaceSecurityError):
        propose_patch("../escape.py", new_content="bad", workspace_root=temp_workspace)

    with pytest.raises(WorkspaceSecurityError):
        validate_workspace_path(temp_workspace / ".git" / "config", workspace_root=temp_workspace)


def test_apply_patch_requires_explicit_confirmation(temp_workspace):
    """Verify apply_patch refuses execution when confirm=False."""
    test_file = temp_workspace / "confirm_test.py"
    test_file.write_text("x = 1\n", encoding="utf-8")

    proposal = propose_patch(test_file, new_content="x = 2\n", workspace_root=temp_workspace)

    # Calling without confirm=True returns failure
    result = apply_patch(patch_id=proposal.patch_id, workspace_root=temp_workspace, confirm=False)
    assert result.success is False
    assert "Explicit confirmation required" in result.message
    assert test_file.read_text(encoding="utf-8") == "x = 1\n"

    # Calling with raise_errors=True raises ConfirmationRequiredError
    with pytest.raises(ConfirmationRequiredError):
        apply_patch(
            patch_id=proposal.patch_id,
            workspace_root=temp_workspace,
            confirm=False,
            raise_errors=True,
        )


def test_apply_patch_creates_backup_and_applies_cleanly(temp_workspace):
    """Verify apply_patch creates .bak backup and updates file when confirmed."""
    test_file = temp_workspace / "app.py"
    orig_content = "def add(a, b):\n    return a + b\n"
    test_file.write_text(orig_content, encoding="utf-8")

    new_content = "def add(a, b):\n    # Optimized addition\n    return a + b\n"
    proposal = propose_patch(test_file, new_content=new_content, workspace_root=temp_workspace)

    result = apply_patch(
        patch_id=proposal.patch_id,
        workspace_root=temp_workspace,
        confirm=True,
    )

    assert result.success is True
    assert result.syntax_check_passed is True
    assert result.rolled_back is False

    # Check updated file content
    assert test_file.read_text(encoding="utf-8") == new_content

    # Check backup file existence and content
    backup_file = test_file.with_name("app.py.bak")
    assert backup_file.exists()
    assert backup_file.read_text(encoding="utf-8") == orig_content


def test_apply_patch_syntax_error_triggers_automatic_rollback(temp_workspace):
    """Verify that invalid syntax triggers an automatic rollback restoring original content."""
    test_file = temp_workspace / "valid.py"
    orig_content = "print('Hello world!')\n"
    test_file.write_text(orig_content, encoding="utf-8")

    # Broken python syntax: missing closing quote and parenthesis
    broken_content = "print('Broken syntax\n"
    proposal = propose_patch(test_file, new_content=broken_content, workspace_root=temp_workspace)

    result = apply_patch(
        patch_id=proposal.patch_id,
        workspace_root=temp_workspace,
        confirm=True,
        run_syntax_check=True,
    )

    # Patch should fail and trigger automatic rollback
    assert result.success is False
    assert result.syntax_check_passed is False
    assert result.rolled_back is True
    assert "Syntax validation failed" in result.message
    assert result.syntax_error is not None

    # Target file must have been restored to original state!
    assert test_file.read_text(encoding="utf-8") == orig_content

    # Backup file remains available for inspection
    backup_file = test_file.with_name("valid.py.bak")
    assert backup_file.exists()
    assert backup_file.read_text(encoding="utf-8") == orig_content


def test_apply_patch_with_unified_diff(temp_workspace):
    """Verify applying a raw unified diff string."""
    test_file = temp_workspace / "diff_test.txt"
    test_file.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")

    diff_str = (
        "--- a/diff_test.txt\n"
        "+++ b/diff_test.txt\n"
        "@@ -1,3 +1,3 @@\n"
        " line 1\n"
        "-line 2\n"
        "+line 2 modified\n"
        " line 3\n"
    )

    result = apply_patch(
        file_path=test_file,
        patch_diff=diff_str,
        workspace_root=temp_workspace,
        confirm=True,
    )

    assert result.success is True
    assert test_file.read_text(encoding="utf-8") == "line 1\nline 2 modified\nline 3\n"


def test_verify_syntax_helper():
    """Verify standalone verify_syntax for Python and JSON."""
    valid_py = "x = [i for i in range(10)]\n"
    invalid_py = "def bad(:"
    assert verify_syntax(Path("test.py"), valid_py)[0] is True
    assert verify_syntax(Path("test.py"), invalid_py)[0] is False

    valid_json = '{"name": "omnitools", "count": 42}'
    invalid_json = '{"name": "omnitools", incomplete'
    assert verify_syntax(Path("data.json"), valid_json)[0] is True
    assert verify_syntax(Path("data.json"), invalid_json)[0] is False
