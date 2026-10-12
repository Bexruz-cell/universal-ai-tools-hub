"""OmniTools Universal AI Bridge - Git Checkpoints Engine

Production-grade git state preservation, clean diff inspection, and safe rollback.
Provides lightweight tags, branch snapshots, isolated plumbing commit captures of
uncommitted working trees, token-budgeted diff inspection, and zero-data-loss rollback
with automated rescue snapshots.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field


# ==============================================================================
# 1. DOMAIN EXCEPTIONS
# ==============================================================================

class GitCheckpointError(Exception):
    """Base exception for all git checkpoint operations."""
    pass


class NotAGitRepositoryError(GitCheckpointError):
    """Raised when an operation is attempted outside a valid git repository."""
    pass


class GitCommandError(GitCheckpointError):
    """Raised when an underlying git subprocess command fails."""

    def __init__(
        self,
        message: str,
        cmd: Optional[List[str]] = None,
        returncode: int = 1,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        super().__init__(message)
        self.cmd = cmd or []
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class CheckpointNotFoundError(GitCheckpointError):
    """Raised when a specified checkpoint tag, branch, or ref cannot be found."""
    pass


class DirtyWorkingTreeError(GitCheckpointError):
    """Raised when uncommitted changes would be overwritten without safe/force mode."""
    pass


class InvalidRefError(GitCheckpointError):
    """Raised when a checkpoint name or git reference is invalid."""
    pass


# ==============================================================================
# 2. ENUMS & PYDANTIC DATA MODELS
# ==============================================================================

class CheckpointType(str, Enum):
    """Type of checkpoint representation in Git."""
    TAG = "tag"             # Lightweight or annotated git tag
    BRANCH = "branch"       # Dedicated checkpoint branch (e.g. chk-branch/*)
    SNAPSHOT = "snapshot"   # Plumbing snapshot commit capturing dirty working tree


class RollbackMode(str, Enum):
    """Rollback execution strategy."""
    SAFE = "safe"           # Auto-creates rescue checkpoint first, then hard resets
    HARD = "hard"           # Hard reset (git reset --hard)
    SOFT = "soft"           # Moves HEAD, keeps index and working tree untouched
    MIXED = "mixed"         # Moves HEAD, unstages index, keeps working tree untouched
    RESTORE = "restore"     # Selectively restores files without moving branch pointer


class CheckpointMetadata(BaseModel):
    """Full metadata model for a captured checkpoint."""
    checkpoint_id: str = Field(..., description="Unique checkpoint identifier (e.g. chk-20261012-173000-refactor)")
    ref_name: str = Field(..., description="Full git ref (e.g. refs/tags/chk/... or refs/heads/chk-branch/...)")
    checkpoint_type: CheckpointType = Field(..., description="Representation type")
    commit_hash: str = Field(..., description="Target commit SHA-1")
    parent_hash: Optional[str] = Field(default=None, description="Parent commit SHA-1")
    created_at: str = Field(..., description="ISO 8601 UTC creation timestamp")
    branch_name: str = Field(..., description="Active git branch when checkpoint was made")
    is_dirty: bool = Field(default=False, description="Whether working tree had uncommitted modifications")
    message: str = Field(..., description="Checkpoint message or intent description")
    files_snapshot: Optional[List[str]] = Field(default=None, description="List of files captured in checkpoint")


class DiffFileStat(BaseModel):
    """Per-file diff statistics."""
    file_path: str = Field(..., description="Relative file path")
    status: str = Field(..., description="Change status: 'added', 'modified', 'deleted', 'renamed'")
    additions: int = Field(default=0, description="Lines added")
    deletions: int = Field(default=0, description="Lines deleted")
    is_binary: bool = Field(default=False, description="True if binary file")


class DiffResult(BaseModel):
    """Clean, structured diff result with token-budget protection."""
    base_ref: str = Field(..., description="Base git reference or commit")
    target_ref: Optional[str] = Field(default=None, description="Target ref (None = working tree)")
    files_changed: int = Field(default=0, description="Total number of modified files")
    total_additions: int = Field(default=0, description="Total lines added")
    total_deletions: int = Field(default=0, description="Total lines deleted")
    file_stats: List[DiffFileStat] = Field(default_factory=list, description="Detailed per-file statistics")
    diff_unified: str = Field(default="", description="Unified diff patch content")
    is_truncated: bool = Field(default=False, description="True if output was truncated to fit line budget")
    truncated_lines: int = Field(default=0, description="Count of omitted lines if truncated")


class RollbackResult(BaseModel):
    """Execution report for a rollback operation."""
    success: bool = Field(..., description="Whether rollback succeeded")
    target_checkpoint_id: str = Field(..., description="Checkpoint ID rolled back to")
    target_commit_hash: str = Field(..., description="Target commit SHA")
    mode: RollbackMode = Field(..., description="Rollback mode executed")
    rescue_checkpoint_id: Optional[str] = Field(default=None, description="Rescue checkpoint ID if created")
    restored_files: List[str] = Field(default_factory=list, description="Files restored or changed")
    message: str = Field(..., description="Summary message of the operation")


# ==============================================================================
# 3. CORE ENGINE: GitCheckpointManager
# ==============================================================================

class GitCheckpointManager:
    """Production-grade manager for git checkpoints, diffs, and safe rollbacks."""

    CACHE_FILENAME = "omni_checkpoints.json"

    def __init__(
        self,
        repo_path: Optional[Union[str, Path]] = None,
        tag_prefix: str = "chk/",
        branch_prefix: str = "chk-branch/",
    ) -> None:
        """Initialize the checkpoint manager.
        
        Args:
            repo_path: Path within git repository. If None, auto-discovers from current dir.
            tag_prefix: Git tag namespace prefix.
            branch_prefix: Git branch namespace prefix.
        """
        self.tag_prefix = tag_prefix
        self.branch_prefix = branch_prefix
        self.repo_root = self._resolve_repo_root(repo_path)
        self._cache_file = self.repo_root / ".git" / self.CACHE_FILENAME

    def _resolve_repo_root(self, path: Optional[Union[str, Path]]) -> Path:
        """Find the root directory of the Git repository."""
        start_dir = Path(path).resolve() if path else Path.cwd().resolve()
        ret, stdout, _ = self._run_git_raw(
            ["rev-parse", "--show-toplevel"],
            cwd=start_dir,
        )
        if ret != 0 or not stdout:
            raise NotAGitRepositoryError(f"Directory '{start_dir}' is not inside a git repository.")
        return Path(stdout.strip()).resolve()

    def _run_git_raw(
        self,
        args: List[str],
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
    ) -> Tuple[int, str, str]:
        """Execute a git command using secure subprocess invocation."""
        work_dir = str(cwd or getattr(self, "repo_root", Path.cwd()))
        run_env = os.environ.copy()
        if env:
            run_env.update(env)
        run_env["GIT_TERMINAL_PROMPT"] = "0"
        run_env["GIT_PAGER"] = "cat"

        cmd = ["git"] + args
        try:
            proc = subprocess.run(
                cmd,
                cwd=work_dir,
                env=run_env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                shell=False,
            )
            return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
        except subprocess.TimeoutExpired as exc:
            return -1, "", f"Git command timed out after {timeout}s: {' '.join(cmd)}"
        except FileNotFoundError:
            return 127, "", "Git binary not found in system PATH."

    def _run_git(
        self,
        args: List[str],
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
        check: bool = True,
    ) -> Tuple[int, str, str]:
        """Execute a git command and optionally verify returncode."""
        ret, stdout, stderr = self._run_git_raw(args, cwd=cwd, env=env, timeout=timeout)
        if check and ret != 0:
            cmd_str = " ".join(["git"] + args)
            raise GitCommandError(
                f"Command '{cmd_str}' failed with code {ret}: {stderr or stdout}",
                cmd=["git"] + args,
                returncode=ret,
                stdout=stdout,
                stderr=stderr,
            )
        return ret, stdout, stderr

    # --------------------------------------------------------------------------
    # Repository Inspection Helpers
    # --------------------------------------------------------------------------

    def get_current_head(self) -> str:
        """Return the current HEAD commit hash (40-character hex)."""
        _, out, _ = self._run_git(["rev-parse", "HEAD"], check=True)
        return out.strip()

    def get_current_branch(self) -> str:
        """Return the active branch name, or 'HEAD' if detached."""
        ret, out, _ = self._run_git_raw(["symbolic-ref", "--short", "HEAD"])
        if ret == 0 and out:
            return out.strip()
        return "HEAD"

    def is_dirty(self) -> bool:
        """Check if working tree contains uncommitted changes (staged or unstaged)."""
        _, out, _ = self._run_git(["status", "--porcelain"], check=True)
        return len(out.strip()) > 0

    def get_status_summary(self) -> Dict[str, Any]:
        """Return a structured overview of uncommitted working tree changes."""
        _, out, _ = self._run_git(["status", "--porcelain"], check=True)
        lines = [line.strip() for line in out.splitlines() if line.strip()]
        modified: List[str] = []
        untracked: List[str] = []
        staged: List[str] = []

        for line in lines:
            if len(line) < 3:
                continue
            idx = line[0]
            work = line[1]
            fname = line[3:].strip()
            if idx == "?" and work == "?":
                untracked.append(fname)
            else:
                if idx in ("M", "A", "D", "R"):
                    staged.append(fname)
                if work in ("M", "D"):
                    modified.append(fname)

        return {
            "is_dirty": len(lines) > 0,
            "total_changed": len(lines),
            "staged": staged,
            "modified": modified,
            "untracked": untracked,
        }

    # --------------------------------------------------------------------------
    # Checkpoint ID & Ref Helpers
    # --------------------------------------------------------------------------

    def _sanitize_name(self, name: str) -> str:
        """Sanitize an arbitrary user string into a safe git tag/branch slug."""
        clean = re.sub(r"[^a-zA-Z0-9_\-\.]", "-", name)
        clean = re.sub(r"-+", "-", clean).strip("-.")
        return clean or "unnamed"

    def _generate_id(self, name: Optional[str] = None) -> str:
        """Generate a deterministic, timestamped checkpoint identifier."""
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
        if name:
            slug = self._sanitize_name(name)
            if slug.startswith("chk-"):
                return slug
            return f"chk-{now_str}-{slug}"
        return f"chk-{now_str}"

    def _tag_name(self, checkpoint_id: str) -> str:
        """Construct git tag name for checkpoint."""
        return f"{self.tag_prefix}{checkpoint_id}"

    def _branch_name(self, checkpoint_id: str) -> str:
        """Construct git branch name for checkpoint."""
        return f"{self.branch_prefix}{checkpoint_id}"

    # --------------------------------------------------------------------------
    # Metadata Cache Management
    # --------------------------------------------------------------------------

    def _load_cache(self) -> Dict[str, Dict[str, Any]]:
        """Load persistent checkpoint metadata cache."""
        if not self._cache_file.exists():
            return {}
        try:
            with open(self._cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_cache(self, cache: Dict[str, Dict[str, Any]]) -> None:
        """Save persistent checkpoint metadata cache."""
        try:
            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # --------------------------------------------------------------------------
    # Checkpoint Creation Engine
    # --------------------------------------------------------------------------

    def create_checkpoint(
        self,
        name: Optional[str] = None,
        checkpoint_type: Union[CheckpointType, str] = CheckpointType.TAG,
        include_uncommitted: bool = True,
        message: Optional[str] = None,
    ) -> CheckpointMetadata:
        """Create a new checkpoint (lightweight tag, branch, or plumbing snapshot).
        
        If `include_uncommitted` is True and the working tree is dirty, captures
        the full working tree state (including unstaged and untracked files) into
        an isolated snapshot commit via temporary git index plumbing, without
        modifying the user's active branch or HEAD.
        """
        if isinstance(checkpoint_type, str):
            checkpoint_type = CheckpointType(checkpoint_type)

        checkpoint_id = self._generate_id(name)
        head_commit = self.get_current_head()
        current_branch = self.get_current_branch()
        dirty = self.is_dirty()
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        desc = message or f"Checkpoint {checkpoint_id}"

        target_commit = head_commit
        parent_hash = head_commit
        actual_type = checkpoint_type
        captured_files: Optional[List[str]] = None

        if dirty and include_uncommitted:
            # Plumbing snapshot: create tree object using a temporary index file
            # This completely avoids touching the real index (.git/index) or working tree!
            temp_idx = self.repo_root / ".git" / f"temp_index_{uuid.uuid4().hex}"
            snap_env = {"GIT_INDEX_FILE": str(temp_idx)}
            try:
                # 1. Populate temp index with current HEAD tree
                self._run_git(["read-tree", "HEAD"], env=snap_env, check=True)
                # 2. Stage all modifications and untracked files into temp index
                self._run_git(["add", "-A"], env=snap_env, check=True)
                # 3. Write tree object
                _, tree_sha, _ = self._run_git(["write-tree"], env=snap_env, check=True)
                # 4. Commit tree with current HEAD as parent
                commit_msg = f"{desc} [snapshot with dirty worktree]"
                _, commit_sha, _ = self._run_git(
                    ["commit-tree", tree_sha.strip(), "-p", head_commit, "-m", commit_msg],
                    env=snap_env,
                    check=True,
                )
                target_commit = commit_sha.strip()
                actual_type = CheckpointType.SNAPSHOT

                # Discover captured files in snapshot
                _, tree_files_out, _ = self._run_git(
                    ["ls-tree", "-r", "--name-only", target_commit],
                    check=False,
                )
                if tree_files_out:
                    captured_files = [f.strip() for f in tree_files_out.splitlines() if f.strip()]
            finally:
                if temp_idx.exists():
                    try:
                        temp_idx.unlink(missing_ok=True)
                    except OSError:
                        pass
        else:
            actual_type = checkpoint_type

        # Create tag or branch ref
        if checkpoint_type == CheckpointType.BRANCH:
            branch_ref = self._branch_name(checkpoint_id)
            self._run_git(["branch", branch_ref, target_commit], check=True)
            full_ref = f"refs/heads/{branch_ref}"
        else:
            tag_ref = self._tag_name(checkpoint_id)
            self._run_git(["tag", tag_ref, target_commit], check=True)
            full_ref = f"refs/tags/{tag_ref}"

        meta = CheckpointMetadata(
            checkpoint_id=checkpoint_id,
            ref_name=full_ref,
            checkpoint_type=actual_type,
            commit_hash=target_commit,
            parent_hash=parent_hash if parent_hash != target_commit else None,
            created_at=created_at,
            branch_name=current_branch,
            is_dirty=dirty,
            message=desc,
            files_snapshot=captured_files,
        )

        # Update cache
        cache = self._load_cache()
        cache[checkpoint_id] = meta.model_dump()
        self._save_cache(cache)

        return meta

    # --------------------------------------------------------------------------
    # Ref Resolution Helper
    # --------------------------------------------------------------------------

    def resolve_ref(self, ref_or_id: str) -> str:
        """Resolve a checkpoint ID, tag name, branch name, or commit SHA into a valid git ref."""
        clean = ref_or_id.strip()
        # 1. Check cache for matching checkpoint_id
        cache = self._load_cache()
        if clean in cache:
            return cache[clean]["commit_hash"]

        # 2. Check tag with tag_prefix
        tag_candidate = self._tag_name(clean)
        ret, out, _ = self._run_git_raw(["rev-parse", "--verify", f"refs/tags/{tag_candidate}"])
        if ret == 0 and out:
            return out.strip()

        # 3. Check branch with branch_prefix
        branch_candidate = self._branch_name(clean)
        ret, out, _ = self._run_git_raw(["rev-parse", "--verify", f"refs/heads/{branch_candidate}"])
        if ret == 0 and out:
            return out.strip()

        # 4. Check verbatim ref or commit SHA
        ret, out, _ = self._run_git_raw(["rev-parse", "--verify", f"{clean}^{{commit}}"])
        if ret == 0 and out:
            return out.strip()

        # 5. Check if it's already a full ref
        ret, out, _ = self._run_git_raw(["rev-parse", "--verify", clean])
        if ret == 0 and out:
            return out.strip()

        raise CheckpointNotFoundError(f"Checkpoint or Git reference '{ref_or_id}' could not be resolved.")

    # --------------------------------------------------------------------------
    # Diff Inspection Engine
    # --------------------------------------------------------------------------

    def inspect_diff(
        self,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        paths: Optional[List[str]] = None,
        max_lines: int = 500,
        cached: bool = False,
    ) -> DiffResult:
        """Inspect git diff cleanly with structured statistics and token-budget protection.
        
        Args:
            base_ref: Base checkpoint ID or git ref (defaults to HEAD).
            target_ref: Target checkpoint ID or git ref (if None, compares to working tree).
            paths: Optional list of file paths to limit diff scope.
            max_lines: Maximum lines of unified diff before truncation kicks in.
            cached: If True and target_ref is None, diff staged index against base_ref.
        """
        # Resolve base ref
        base_resolved = self.resolve_ref(base_ref) if base_ref else "HEAD"
        target_resolved = self.resolve_ref(target_ref) if target_ref else None

        # Build git diff arguments
        diff_args: List[str] = []
        if target_resolved:
            diff_args = [base_resolved, target_resolved]
        else:
            if cached:
                diff_args = ["--cached", base_resolved]
            else:
                diff_args = [base_resolved]

        path_args: List[str] = ["--"] + [str(p) for p in paths] if paths else []

        # 1. Collect numstat stats
        _, numstat_out, _ = self._run_git(["diff", "--numstat"] + diff_args + path_args, check=True)
        # 2. Collect name-status
        _, status_out, _ = self._run_git(["diff", "--name-status"] + diff_args + path_args, check=True)
        # 3. Collect unified patch
        _, patch_out, _ = self._run_git(["diff", "-p"] + diff_args + path_args, check=True)

        # Parse status map
        status_map: Dict[str, str] = {}
        for line in status_out.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) == 2:
                code = parts[0][0].upper()
                fname = parts[1].strip()
                status_label = {
                    "A": "added",
                    "M": "modified",
                    "D": "deleted",
                    "R": "renamed",
                    "C": "copied",
                }.get(code, "modified")
                status_map[fname] = status_label

        file_stats: List[DiffFileStat] = []
        total_adds = 0
        total_dels = 0

        for line in numstat_out.splitlines():
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                raw_adds, raw_dels, fname = parts[0], parts[1], parts[2]
                is_bin = (raw_adds == "-" or raw_dels == "-")
                adds = int(raw_adds) if not is_bin else 0
                dels = int(raw_dels) if not is_bin else 0
                total_adds += adds
                total_dels += dels
                stat_entry = DiffFileStat(
                    file_path=fname,
                    status=status_map.get(fname, "modified"),
                    additions=adds,
                    deletions=dels,
                    is_binary=is_bin,
                )
                file_stats.append(stat_entry)

        # Apply token budget / line truncation guard
        patch_lines = patch_out.splitlines()
        is_truncated = False
        truncated_count = 0
        if len(patch_lines) > max_lines:
            truncated_count = len(patch_lines) - max_lines
            is_truncated = True
            omitted_msg = (
                f"\n\n[Diff truncated: showing {max_lines} of {len(patch_lines)} lines. "
                f"{truncated_count} lines omitted for token context hygiene]"
            )
            unified_diff = "\n".join(patch_lines[:max_lines]) + omitted_msg
        else:
            unified_diff = patch_out

        return DiffResult(
            base_ref=base_ref or "HEAD",
            target_ref=target_ref,
            files_changed=len(file_stats),
            total_additions=total_adds,
            total_deletions=total_dels,
            file_stats=file_stats,
            diff_unified=unified_diff,
            is_truncated=is_truncated,
            truncated_lines=truncated_count,
        )

    # --------------------------------------------------------------------------
    # Rollback Engine
    # --------------------------------------------------------------------------

    def rollback(
        self,
        checkpoint_id: str,
        mode: Union[RollbackMode, str] = RollbackMode.SAFE,
        file_paths: Optional[List[str]] = None,
        force: bool = False,
    ) -> RollbackResult:
        """Rollback repository state to a checkpoint with safety guarantees.
        
        Args:
            checkpoint_id: Identifier of target checkpoint (or tag, branch, commit).
            mode: RollbackMode (safe, hard, soft, mixed, restore).
            file_paths: Specific files to restore (for partial rollback).
            force: Allow hard reset even if working tree is dirty without safe rescue.
        """
        if isinstance(mode, str):
            mode = RollbackMode(mode)

        target_commit = self.resolve_ref(checkpoint_id)
        dirty = self.is_dirty()
        rescue_id: Optional[str] = None

        if dirty:
            if mode == RollbackMode.SAFE:
                # Guaranteed zero data loss: auto-create rescue snapshot
                ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
                rescue_name = f"rescue-before-rollback-{ts}"
                rescue_meta = self.create_checkpoint(
                    name=rescue_name,
                    checkpoint_type=CheckpointType.TAG,
                    include_uncommitted=True,
                    message=f"Automatic rescue snapshot before rollback to {checkpoint_id}",
                )
                rescue_id = rescue_meta.checkpoint_id
            elif mode == RollbackMode.HARD and not force:
                raise DirtyWorkingTreeError(
                    f"Working tree has uncommitted modifications. Rollback with mode='hard' "
                    f"requires force=True, or use mode='safe' for automated rescue protection."
                )

        restored_files: List[str] = []

        if file_paths:
            # File-selective restoration
            target_args = ["checkout", target_commit, "--"] + [str(p) for p in file_paths]
            self._run_git(target_args, check=True)
            restored_files = [str(p) for p in file_paths]
            msg = f"Restored {len(restored_files)} files from checkpoint {checkpoint_id} ({target_commit[:8]})."
        else:
            # Branch / tree level rollback
            if mode in (RollbackMode.SAFE, RollbackMode.HARD):
                self._run_git(["reset", "--hard", target_commit], check=True)
                restored_files = ["<full-working-tree>"]
                msg = f"Hard reset working tree and HEAD to checkpoint {checkpoint_id} ({target_commit[:8]})."
            elif mode == RollbackMode.SOFT:
                self._run_git(["reset", "--soft", target_commit], check=True)
                restored_files = ["<HEAD-moved>"]
                msg = f"Soft reset HEAD to checkpoint {checkpoint_id} ({target_commit[:8]}); index and worktree preserved."
            elif mode == RollbackMode.MIXED:
                self._run_git(["reset", "--mixed", target_commit], check=True)
                restored_files = ["<index-reset>"]
                msg = f"Mixed reset HEAD and index to checkpoint {checkpoint_id} ({target_commit[:8]}); worktree preserved."
            elif mode == RollbackMode.RESTORE:
                self._run_git(["checkout", target_commit, "--", "."], check=True)
                restored_files = ["<all-tracked-files>"]
                msg = f"Restored all tracked files to checkpoint {checkpoint_id} ({target_commit[:8]}); HEAD unmoved."
            else:
                raise ValueError(f"Unsupported rollback mode: {mode}")

        if rescue_id:
            msg += f" (Automatic rescue checkpoint created: {rescue_id})"

        return RollbackResult(
            success=True,
            target_checkpoint_id=checkpoint_id,
            target_commit_hash=target_commit,
            mode=mode,
            rescue_checkpoint_id=rescue_id,
            restored_files=restored_files,
            message=msg,
        )

    # --------------------------------------------------------------------------
    # Checkpoint Discovery & Lifecycle Management
    # --------------------------------------------------------------------------

    def list_checkpoints(self, limit: int = 50, prefix: Optional[str] = None) -> List[CheckpointMetadata]:
        """List historical checkpoints sorted by newest first."""
        cache = self._load_cache()
        items: List[CheckpointMetadata] = []

        # 1. Collect from cache
        for cid, data in cache.items():
            if prefix and not cid.startswith(prefix):
                continue
            try:
                items.append(CheckpointMetadata(**data))
            except Exception:
                pass

        # 2. Discover from git tags (matching tag_prefix) not in cache
        tag_pat = f"{self.tag_prefix}*"
        _, tag_out, _ = self._run_git(["tag", "-l", tag_pat], check=False)
        seen_ids = {item.checkpoint_id for item in items}

        for tag in tag_out.splitlines():
            tag = tag.strip()
            if not tag:
                continue
            cid = tag[len(self.tag_prefix):]
            if cid in seen_ids:
                continue
            # Query commit hash and date
            _, sha_out, _ = self._run_git(["rev-parse", f"refs/tags/{tag}"], check=False)
            _, date_out, _ = self._run_git(["log", "-1", "--format=%cI", f"refs/tags/{tag}"], check=False)
            _, msg_out, _ = self._run_git(["log", "-1", "--format=%s", f"refs/tags/{tag}"], check=False)
            items.append(
                CheckpointMetadata(
                    checkpoint_id=cid,
                    ref_name=f"refs/tags/{tag}",
                    checkpoint_type=CheckpointType.TAG,
                    commit_hash=sha_out.strip() or "unknown",
                    created_at=date_out.strip() or datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    branch_name="unknown",
                    is_dirty=False,
                    message=msg_out.strip() or f"Discovered tag {tag}",
                )
            )

        # Sort newest first
        items.sort(key=lambda x: x.created_at, reverse=True)
        return items[:limit]

    def get_checkpoint(self, checkpoint_id: str) -> Optional[CheckpointMetadata]:
        """Retrieve metadata for a specific checkpoint ID."""
        for chk in self.list_checkpoints(limit=500):
            if chk.checkpoint_id == checkpoint_id:
                return chk
        return None

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint tag and/or branch and remove from cache."""
        deleted = False
        tag_name = self._tag_name(checkpoint_id)
        branch_name = self._branch_name(checkpoint_id)

        # Delete tag if exists
        ret_tag, _, _ = self._run_git_raw(["tag", "-d", tag_name])
        if ret_tag == 0:
            deleted = True

        # Delete branch if exists
        ret_br, _, _ = self._run_git_raw(["branch", "-D", branch_name])
        if ret_br == 0:
            deleted = True

        # Remove from cache
        cache = self._load_cache()
        if checkpoint_id in cache:
            del cache[checkpoint_id]
            self._save_cache(cache)
            deleted = True

        return deleted


# ==============================================================================
# 4. STANDALONE BRIDGE FACADES (FastAPI & MCP Compatible)
# ==============================================================================

def git_create_checkpoint(
    repo_path: Optional[str] = None,
    name: Optional[str] = None,
    message: Optional[str] = None,
    include_uncommitted: bool = True,
    checkpoint_type: str = "tag",
) -> Dict[str, Any]:
    """Create a git checkpoint and return JSON-serializable dictionary."""
    mgr = GitCheckpointManager(repo_path=repo_path)
    meta = mgr.create_checkpoint(
        name=name,
        checkpoint_type=checkpoint_type,
        include_uncommitted=include_uncommitted,
        message=message,
    )
    return meta.model_dump()


def git_inspect_diff(
    repo_path: Optional[str] = None,
    base: Optional[str] = None,
    target: Optional[str] = None,
    paths: Optional[List[str]] = None,
    max_lines: int = 500,
) -> Dict[str, Any]:
    """Inspect git diff and return JSON-serializable dictionary."""
    mgr = GitCheckpointManager(repo_path=repo_path)
    res = mgr.inspect_diff(
        base_ref=base,
        target_ref=target,
        paths=paths,
        max_lines=max_lines,
    )
    return res.model_dump()


def git_rollback(
    checkpoint_id: str,
    repo_path: Optional[str] = None,
    mode: str = "safe",
    file_paths: Optional[List[str]] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Execute a rollback to a target checkpoint."""
    mgr = GitCheckpointManager(repo_path=repo_path)
    res = mgr.rollback(
        checkpoint_id=checkpoint_id,
        mode=mode,
        file_paths=file_paths,
        force=force,
    )
    return res.model_dump()


def git_list_checkpoints(
    repo_path: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """List checkpoints as JSON-serializable dictionaries."""
    mgr = GitCheckpointManager(repo_path=repo_path)
    return [c.model_dump() for c in mgr.list_checkpoints(limit=limit)]


def git_delete_checkpoint(
    checkpoint_id: str,
    repo_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Delete a checkpoint and return status dictionary."""
    mgr = GitCheckpointManager(repo_path=repo_path)
    success = mgr.delete_checkpoint(checkpoint_id)
    return {"checkpoint_id": checkpoint_id, "deleted": success}


def git_checkpoint(
    action: str = "create",
    *,
    repo_path: Optional[Union[str, Path]] = None,
    name: Optional[str] = None,
    message: Optional[str] = None,
    include_uncommitted: bool = True,
    checkpoint_type: str = "tag",
    checkpoint_id: Optional[str] = None,
    mode: str = "safe",
    base: Optional[str] = None,
    target: Optional[str] = None,
    file_paths: Optional[List[str]] = None,
    max_lines: int = 500,
    force: bool = False,
    limit: int = 50,
) -> Dict[str, Any]:
    """Unified entrypoint for all git checkpoint operations.
    
    Actions:
      - 'create': Create a lightweight tag, branch, or plumbing snapshot.
      - 'diff' or 'inspect': Inspect diff cleanly with token-budget protection.
      - 'rollback': Revert state safely with automatic rescue snapshot.
      - 'list': List historical checkpoints.
      - 'get': Retrieve metadata for a specific checkpoint.
      - 'delete': Delete an existing checkpoint.
    """
    mgr = GitCheckpointManager(repo_path=repo_path)
    act = action.lower().strip()

    if act == "create":
        meta = mgr.create_checkpoint(
            name=name,
            checkpoint_type=checkpoint_type,
            include_uncommitted=include_uncommitted,
            message=message,
        )
        d = meta.model_dump()
        d["status"] = "success"
        return d

    elif act in ("diff", "inspect"):
        res = mgr.inspect_diff(
            base_ref=base,
            target_ref=target,
            paths=file_paths,
            max_lines=max_lines,
        )
        d = res.model_dump()
        d["status"] = "success"
        return d

    elif act == "rollback":
        if not checkpoint_id:
            raise ValueError("action='rollback' requires 'checkpoint_id'.")
        res = mgr.rollback(
            checkpoint_id=checkpoint_id,
            mode=mode,
            file_paths=file_paths,
            force=force,
        )
        d = res.model_dump()
        d["status"] = "success" if res.success else "error"
        return d

    elif act == "list":
        chks = [c.model_dump() for c in mgr.list_checkpoints(limit=limit)]
        for c in chks:
            c["id"] = c.get("checkpoint_id")
        return {"status": "success", "checkpoints": chks}

    elif act == "get":
        if not checkpoint_id:
            raise ValueError("action='get' requires 'checkpoint_id'.")
        chk = mgr.get_checkpoint(checkpoint_id)
        if not chk:
            raise CheckpointNotFoundError(f"Checkpoint '{checkpoint_id}' not found.")
        d = chk.model_dump()
        d["status"] = "success"
        return d

    elif act == "delete":
        if not checkpoint_id:
            raise ValueError("action='delete' requires 'checkpoint_id'.")
        success = mgr.delete_checkpoint(checkpoint_id)
        return {"status": "success" if success else "error", "checkpoint_id": checkpoint_id, "deleted": success}

    else:
        raise ValueError(
            f"Unknown action '{action}'. Supported actions: 'create', 'diff', 'rollback', 'list', 'get', 'delete'."
        )
