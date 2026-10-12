from __future__ import annotations

from pathlib import Path

import pytest

from src.adapters.mcp_adapter import handle_call_tool
from src.security.workspace_policy import WorkspaceAuthorizationError, WorkspacePolicy


def test_policy_rejects_sibling_and_parent_paths(tmp_path: Path):
    workspace = tmp_path / "workspace"
    outside = tmp_path / "workspace-other"
    workspace.mkdir()
    outside.mkdir()
    (workspace / "inside.py").write_text("value = 1\n", encoding="utf-8")
    (outside / "secret.py").write_text("secret = True\n", encoding="utf-8")

    policy = WorkspacePolicy([workspace])
    assert policy.validate(workspace / "inside.py", must_be_file=True)
    with pytest.raises(Exception):
        policy.validate(outside / "secret.py", must_be_file=True)
    with pytest.raises(Exception):
        policy.validate(workspace / ".." / "workspace-other" / "secret.py", must_be_file=True)


def test_policy_rejects_symlink_escape(tmp_path: Path):
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside.txt"
    workspace.mkdir()
    outside.write_text("secret\n", encoding="utf-8")
    link = workspace / "link.txt"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable on this runner")

    policy = WorkspacePolicy([workspace])
    with pytest.raises(Exception):
        policy.validate(link, must_be_file=True)


def test_mcp_repo_map_uses_process_authorized_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    (workspace / "module.py").write_text("value = 1\n", encoding="utf-8")
    monkeypatch.setenv(WorkspacePolicy.ENV_ROOTS, str(workspace))

    allowed = _run_sync_mcp("repo_map", {"root_path": str(workspace), "as_format": "dict"})
    assert "module.py" in allowed

    denied = _run_sync_mcp("repo_map", {"root_path": str(outside), "as_format": "dict"})
    assert "WORKSPACE_ACCESS_DENIED" in denied


def test_mcp_estimate_tokens_rejects_external_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside.txt"
    workspace.mkdir()
    outside.write_text("secret\n", encoding="utf-8")
    monkeypatch.setenv(WorkspacePolicy.ENV_ROOTS, str(workspace))

    result = _run_sync_mcp("estimate_tokens", {"file_paths": [str(outside)]})
    assert "WORKSPACE_ACCESS_DENIED" in result


def _run_sync_mcp(name: str, arguments: dict) -> str:
    """Drive the current synchronous MCP handlers without creating an event loop.

    The production stdio server remains async because legacy web tools await I/O.
    The coding-tool routes themselves contain no await points, so this helper
    exercises their real router entrypoint while avoiding the host runner's
    Windows Python 3.13 event-loop initialization issue.
    """
    coroutine = handle_call_tool(name, arguments)
    try:
        coroutine.send(None)
    except StopIteration as completed:
        return completed.value
    finally:
        coroutine.close()
    raise AssertionError("coding tool unexpectedly suspended")

