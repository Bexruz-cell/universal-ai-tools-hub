"""Fail-closed authorization boundary for MCP filesystem operations."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Union

from .path_guard import PathGuard, SecurityError


class WorkspaceAuthorizationError(SecurityError):
    """Raised when a workspace cannot be independently authorized."""


def _canonical_root(value: Union[str, Path]) -> Path:
    raw = str(value)
    if not raw or "\x00" in raw:
        raise WorkspaceAuthorizationError("Workspace root is empty or contains a null byte.")
    path = Path(raw)
    if not path.is_absolute():
        path = Path.cwd() / path
    try:
        return path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise WorkspaceAuthorizationError(f"Cannot establish workspace root: {value}") from exc


class WorkspacePolicy:
    """Authorize tool paths against roots established by process state."""

    ENV_ROOTS = "OMNITOOLS_AUTHORIZED_ROOTS"

    def __init__(self, roots: Iterable[Union[str, Path]]) -> None:
        canonical = [_canonical_root(root) for root in roots]
        if not canonical:
            raise WorkspaceAuthorizationError("No authorized workspace roots were provided.")
        self.roots = tuple(dict.fromkeys(canonical))
        self.guard = PathGuard(workspace_root=self.roots[0], allowed_roots=self.roots)

    @classmethod
    def from_process(cls) -> "WorkspacePolicy":
        configured = os.environ.get(cls.ENV_ROOTS, "")
        roots = [item for item in configured.split(os.pathsep) if item.strip()]
        return cls(roots or [Path.cwd()])

    def validate(self, target: Union[str, Path, None], **kwargs) -> Path:
        if target is None or not str(target).strip():
            raise WorkspaceAuthorizationError("A workspace path is required.")
        return self.guard.validate_path(target, **kwargs)

