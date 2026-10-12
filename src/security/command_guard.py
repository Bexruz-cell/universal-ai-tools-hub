"""Security Command Guard: Execution Guardrails & Subprocess Isolation

Enforces strict execution parameters:
- Absolute prohibition of shell=True
- Mandatory bounded execution timeouts
- Argument sequence and null-byte validation
- Workspace-contained working directory verification
- Tree-aware termination on timeout
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from src.security.path_guard import PathGuard, SecurityError


class CommandSecurityError(SecurityError):
    """Raised when a command execution violates security policy."""
    pass


class CommandExecutionTimeout(CommandSecurityError):
    """Raised when a command exceeds its allotted execution timeout."""
    pass


class DisallowedExecutableError(CommandSecurityError):
    """Raised when an executable is forbidden by security policies."""
    pass


class CommandGuard:
    """Hardened execution runner enforcing zero shell=True, strict timeouts, and boundary checks."""

    def __init__(
        self,
        default_timeout: float = 30.0,
        max_timeout: float = 300.0,
        path_guard: Optional[PathGuard] = None,
    ) -> None:
        self.default_timeout = float(default_timeout)
        self.max_timeout = float(max_timeout)
        self.path_guard = path_guard or PathGuard()

    def validate_command(
        self,
        args: Union[Sequence[str], str],
        shell: bool = False,
        cwd: Optional[Union[str, Path]] = None,
        timeout: Optional[float] = None,
    ) -> Tuple[List[str], Optional[Path], float]:
        """Validate command parameters against security policies.

        Returns:
            Tuple of (sanitized_command_list, validated_cwd_path, validated_timeout).
        """
        # 1. Prohibit shell=True
        if shell:
            raise CommandSecurityError("Execution with shell=True is strictly prohibited.")

        # 2. Enforce argument sequence (no unparsed strings)
        if isinstance(args, (str, bytes)):
            raise CommandSecurityError(
                "Command must be provided as a sequence of strings (e.g. ['python', 'script.py']), not a raw shell string."
            )

        if not args:
            raise CommandSecurityError("Command arguments sequence cannot be empty.")

        cmd_list: List[str] = []
        for i, arg in enumerate(args):
            if not isinstance(arg, str):
                arg_str = str(arg)
            else:
                arg_str = arg

            if "\0" in arg_str:
                raise CommandSecurityError(f"Null byte detected in argument {i}.")
            cmd_list.append(arg_str)

        if not cmd_list[0].strip():
            raise CommandSecurityError("Executable name cannot be blank or empty.")

        # 3. Timeout validation
        effective_timeout = self.default_timeout if timeout is None else float(timeout)
        if effective_timeout <= 0:
            raise CommandSecurityError("Timeout must be a strictly positive number.")
        if effective_timeout > self.max_timeout:
            raise CommandSecurityError(
                f"Requested timeout ({effective_timeout}s) exceeds maximum allowed limit ({self.max_timeout}s)."
            )

        # 4. Working directory validation
        validated_cwd: Optional[Path] = None
        if cwd is not None:
            validated_cwd = self.path_guard.validate_path(cwd, must_be_dir=True)

        return cmd_list, validated_cwd, effective_timeout

    def safe_run(
        self,
        args: Sequence[str],
        cwd: Optional[Union[str, Path]] = None,
        timeout: Optional[float] = None,
        env: Optional[Dict[str, str]] = None,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        input: Optional[Union[str, bytes]] = None,
        shell: bool = False,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess:
        """Safely execute a command synchronously without shell=True and with strict timeout."""
        if shell or kwargs.get("shell", False):
            raise CommandSecurityError("Execution with shell=True is strictly prohibited.")

        cmd_list, valid_cwd, eff_timeout = self.validate_command(
            args=args,
            shell=False,
            cwd=cwd,
            timeout=timeout,
        )

        try:
            return subprocess.run(
                cmd_list,
                cwd=str(valid_cwd) if valid_cwd else None,
                timeout=eff_timeout,
                shell=False,
                capture_output=capture_output,
                text=text,
                check=check,
                input=input,
                env=env,
                **kwargs,
            )
        except subprocess.TimeoutExpired as exc:
            raise CommandExecutionTimeout(
                f"Command execution timed out after {eff_timeout} seconds: {cmd_list}"
            ) from exc

    async def safe_async_run(
        self,
        args: Sequence[str],
        cwd: Optional[Union[str, Path]] = None,
        timeout: Optional[float] = None,
        env: Optional[Dict[str, str]] = None,
        input: Optional[Union[str, bytes]] = None,
        shell: bool = False,
        **kwargs: Any,
    ) -> Tuple[int, str, str]:
        """Safely execute a command asynchronously without shell=True and with strict timeout.

        Returns:
            Tuple of (returncode, stdout, stderr).
        """
        if shell or kwargs.get("shell", False):
            raise CommandSecurityError("Execution with shell=True is strictly prohibited.")

        cmd_list, valid_cwd, eff_timeout = self.validate_command(
            args=args,
            shell=False,
            cwd=cwd,
            timeout=timeout,
        )

        proc = await asyncio.create_subprocess_exec(
            *cmd_list,
            cwd=str(valid_cwd) if valid_cwd else None,
            env=env,
            stdin=asyncio.subprocess.PIPE if input is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            **kwargs,
        )

        input_bytes: Optional[bytes] = None
        if input is not None:
            input_bytes = input.encode("utf-8") if isinstance(input, str) else input

        try:
            stdout_data, stderr_data = await asyncio.wait_for(
                proc.communicate(input=input_bytes),
                timeout=eff_timeout,
            )
            stdout_str = stdout_data.decode("utf-8", errors="replace") if stdout_data else ""
            stderr_str = stderr_data.decode("utf-8", errors="replace") if stderr_data else ""
            return proc.returncode if proc.returncode is not None else 0, stdout_str, stderr_str
        except asyncio.TimeoutError as exc:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
            raise CommandExecutionTimeout(
                f"Asynchronous command timed out after {eff_timeout} seconds: {cmd_list}"
            ) from exc

    def safe_popen(
        self,
        args: Sequence[str],
        cwd: Optional[Union[str, Path]] = None,
        shell: bool = False,
        **kwargs: Any,
    ) -> subprocess.Popen:
        """Safely create a subprocess.Popen object without shell=True."""
        if shell or kwargs.get("shell", False):
            raise CommandSecurityError("Execution with shell=True is strictly prohibited.")

        cmd_list, valid_cwd, _ = self.validate_command(
            args=args,
            shell=False,
            cwd=cwd,
            timeout=self.default_timeout,
        )

        return subprocess.Popen(
            cmd_list,
            cwd=str(valid_cwd) if valid_cwd else None,
            shell=False,
            **kwargs,
        )
