"""Security Path Guard: Workspace Boundary and Traversal Defense

Enforces strict directory containment, canonical path resolution,
symlink escape mitigation, null-byte rejection, and Windows-specific
reserved device sanitization.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Optional, Sequence, Union

# Windows reserved DOS device names: CON, PRN, AUX, NUL, COM1-9, LPT1-9, CONIN$, CONOUT$
WINDOWS_RESERVED_NAMES = re.compile(
    r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]|CONIN\$|CONOUT\$)(\..*)?$",
    re.IGNORECASE,
)


class SecurityError(Exception):
    """Base security exception."""
    pass


class PathTraversalError(SecurityError):
    """Raised when a path breaches the allowed workspace boundaries or contains traversal patterns."""
    pass


class DisallowedPathError(SecurityError):
    """Raised when a path targets reserved system device names or forbidden system paths."""
    pass


class PathGuard:
    """Guards filesystem access by strictly validating paths against authorized root directories."""

    def __init__(
        self,
        workspace_root: Optional[Union[str, Path]] = None,
        allowed_roots: Optional[Sequence[Union[str, Path]]] = None,
    ) -> None:
        if workspace_root is None:
            # Default to repository root (parent of src)
            workspace_root = Path(__file__).resolve().parent.parent.parent
        self.workspace_root = Path(workspace_root).resolve()

        self.allowed_roots: list[Path] = [self.workspace_root]
        if allowed_roots:
            for r in allowed_roots:
                resolved_r = Path(r).resolve()
                if resolved_r not in self.allowed_roots:
                    self.allowed_roots.append(resolved_r)

    def is_safe_path(
        self,
        target: Union[str, Path],
        allow_nonexistent: bool = False,
    ) -> bool:
        """Return True if path is safe and contained within allowed roots, False otherwise."""
        try:
            self.validate_path(target, allow_nonexistent=allow_nonexistent)
            return True
        except (SecurityError, ValueError, OSError):
            return False

    def validate_path(
        self,
        target: Union[str, Path],
        allow_nonexistent: bool = False,
        must_be_file: bool = False,
        must_be_dir: bool = False,
    ) -> Path:
        """Validate that a target path resolves safely within allowed workspace boundaries.

        Args:
            target: The file or directory path to validate.
            allow_nonexistent: If True, allow paths whose final component does not yet exist.
            must_be_file: If True, target must exist and be a regular file.
            must_be_dir: If True, target must exist and be a directory.

        Returns:
            The canonical resolved Path object.

        Raises:
            PathTraversalError: If path attempts directory traversal or escapes workspace boundaries.
            DisallowedPathError: If path references DOS device names or illegal characters.
            FileNotFoundError: If path does not exist and allow_nonexistent is False.
        """
        raw_str = str(target)
        if "\0" in raw_str:
            raise PathTraversalError("Null byte injection detected in path.")

        # Check for Windows reserved names in each component
        p_obj = Path(raw_str)
        for part in p_obj.parts:
            # Strip trailing dots or spaces which Windows might strip
            clean_part = part.rstrip(". ")
            if WINDOWS_RESERVED_NAMES.match(clean_part):
                raise DisallowedPathError(f"Target contains Windows reserved device name: '{part}'")

        # Check for Alternative Data Streams (e.g. C:\path\file.txt:stream)
        drive, rest = os.path.splitdrive(raw_str)
        if ":" in rest:
            raise DisallowedPathError(f"Alternate Data Stream syntax disallowed: '{raw_str}'")

        # Resolve path relative to workspace_root if not absolute
        if not p_obj.is_absolute():
            candidate = (self.workspace_root / p_obj)
        else:
            candidate = p_obj

        try:
            # Canonical resolution: resolves symlinks and eliminates ..
            resolved = candidate.resolve()
        except (RuntimeError, OSError) as e:
            raise PathTraversalError(f"Failed to resolve path safely: {e}") from e

        # Boundary Check: Must be relative to at least one allowed root
        is_contained = False
        for root in self.allowed_roots:
            try:
                # Case insensitivity comparison on Windows
                if os.name == "nt":
                    resolved_norm = Path(os.path.normcase(str(resolved)))
                    root_norm = Path(os.path.normcase(str(root)))
                    if resolved_norm.is_relative_to(root_norm):
                        is_contained = True
                        break
                else:
                    if resolved.is_relative_to(root):
                        is_contained = True
                        break
            except (ValueError, AttributeError):
                continue

        if not is_contained:
            raise PathTraversalError(
                f"Path traversal detected: '{target}' resolves to '{resolved}', "
                f"which is outside authorized workspace boundaries."
            )

        if not allow_nonexistent and not resolved.exists():
            raise FileNotFoundError(f"File or directory does not exist: '{target}'")



        if must_be_file:
            if not resolved.is_file():
                raise DisallowedPathError(f"Target path is not a file: '{resolved}'")
        if must_be_dir:
            if not resolved.is_dir():
                raise DisallowedPathError(f"Target path is not a directory: '{resolved}'")

        return resolved

    def safe_read_text(
        self,
        path: Union[str, Path],
        encoding: str = "utf-8",
        max_bytes: int = 10_000_000,
    ) -> str:
        """Safely read text from a file within the workspace boundary."""
        valid_path = self.validate_path(path, must_be_file=True)
        file_size = valid_path.stat().st_size
        if file_size > max_bytes:
            raise SecurityError(f"File size ({file_size} bytes) exceeds safety limit ({max_bytes} bytes).")
        return valid_path.read_text(encoding=encoding)

    def safe_write_text(
        self,
        path: Union[str, Path],
        content: str,
        encoding: str = "utf-8",
    ) -> Path:
        """Safely write text to a file within the workspace boundary."""
        valid_path = self.validate_path(path, allow_nonexistent=True)
        valid_path.parent.mkdir(parents=True, exist_ok=True)
        valid_path.write_text(content, encoding=encoding)
        return valid_path

    def safe_read_bytes(
        self,
        path: Union[str, Path],
        max_bytes: int = 50_000_000,
    ) -> bytes:
        """Safely read binary data from a file within the workspace boundary."""
        valid_path = self.validate_path(path, must_be_file=True)
        file_size = valid_path.stat().st_size
        if file_size > max_bytes:
            raise SecurityError(f"File size ({file_size} bytes) exceeds safety limit ({max_bytes} bytes).")
        return valid_path.read_bytes()

    def safe_write_bytes(
        self,
        path: Union[str, Path],
        content: bytes,
    ) -> Path:
        """Safely write bytes to a file within the workspace boundary."""
        valid_path = self.validate_path(path, allow_nonexistent=True)
        valid_path.parent.mkdir(parents=True, exist_ok=True)
        valid_path.write_bytes(content)
        return valid_path
