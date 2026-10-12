"""OmniTools Universal AI Bridge - Security Module

Provides enterprise-grade boundary guards:
- PathGuard: Enforces workspace isolation, traversal protection, and symlink resolution.
- CommandGuard: Enforces process isolation, no shell=True, argument safety, and strict timeouts.
"""

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
    DisallowedExecutableError,
)
from src.security.workspace_policy import WorkspaceAuthorizationError, WorkspacePolicy

__all__ = [
    "PathGuard",
    "SecurityError",
    "PathTraversalError",
    "DisallowedPathError",
    "CommandGuard",
    "CommandSecurityError",
    "CommandExecutionTimeout",
    "DisallowedExecutableError",
    "WorkspacePolicy",
    "WorkspaceAuthorizationError",
]
