"""OmniTools Universal AI Bridge - Repository Intelligence & Map Engine

Provides compact repository structure analysis, hierarchical directory trees,
file statistics, and primary language breakdowns bounded by max_depth and max_entries
for LLM prompt context injection, FastAPI REST endpoints, and MCP tool protocols.
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# ==============================================================================
# 1. EXCLUSION & FILTERING CONFIGURATION
# ==============================================================================

DEFAULT_EXCLUDED_DIRS: Set[str] = {
    # Version control
    ".git",
    ".svn",
    ".hg",
    # Python & testing caches
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    ".coverage",
    ".hypothesis",
    # Virtual environments & package managers
    ".venv",
    "venv",
    "env",
    ".env",
    "node_modules",
    "site-packages",
    "vendor",
    "bower_components",
    # Build & distribution outputs
    "build",
    "dist",
    "out",
    "target",
    ".next",
    ".nuxt",
    ".turbo",
    ".cache",
    # IDEs & OS metadata
    ".idea",
    ".vscode",
    ".vs",
    ".settings",
    ".DS_Store",
    "Thumbs.db",
}

DEFAULT_EXCLUDED_PATTERNS: List[str] = [
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.so",
    "*.dll",
    "*.dylib",
    "*.class",
    "*.exe",
    "*.o",
    "*.obj",
    "*.egg-info",
    "*.egg",
    ".DS_Store",
    "Thumbs.db",
]

# ==============================================================================
# 2. LANGUAGE CLASSIFICATION MATRIX
# ==============================================================================

EXTENSION_LANGUAGE_MAP: Dict[str, str] = {
    # Python
    ".py": "Python",
    ".pyi": "Python",
    ".pyx": "Python",
    # TypeScript / JavaScript
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    # Systems languages
    ".rs": "Rust",
    ".go": "Go",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".hpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hh": "C++",
    # JVM & .NET
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",
    ".cs": "C#",
    ".fs": "F#",
    # Web & Style
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "Sass",
    ".less": "Less",
    ".vue": "Vue",
    ".svelte": "Svelte",
    # Scripting & Shell
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".ps1": "PowerShell",
    ".psm1": "PowerShell",
    ".rb": "Ruby",
    ".php": "PHP",
    ".pl": "Perl",
    ".lua": "Lua",
    # Data & Configuration
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".xml": "XML",
    ".ini": "INI",
    ".sql": "SQL",
    # Documentation
    ".md": "Markdown",
    ".markdown": "Markdown",
    ".rst": "reStructuredText",
    ".txt": "Text",
}

SPECIAL_FILENAME_LANGUAGE_MAP: Dict[str, str] = {
    "dockerfile": "Dockerfile",
    "containerfile": "Dockerfile",
    "makefile": "Makefile",
    "gnumakefile": "Makefile",
    "cmakelists.txt": "CMake",
    "gemfile": "Ruby",
    "rakefile": "Ruby",
    "vagrantfile": "Ruby",
}


def detect_language(file_name: str) -> Optional[str]:
    """Detect language from file name or extension."""
    lower_name = file_name.lower()
    if lower_name in SPECIAL_FILENAME_LANGUAGE_MAP:
        return SPECIAL_FILENAME_LANGUAGE_MAP[lower_name]

    suffix = Path(lower_name).suffix
    return EXTENSION_LANGUAGE_MAP.get(suffix)


def format_size(size_bytes: int) -> str:
    """Format bytes into human-readable compact string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


# ==============================================================================
# 3. DATA MODELS
# ==============================================================================

@dataclass
class LanguageStats:
    """Language breakdown statistics."""
    language: str
    file_count: int
    total_bytes: int
    percentage: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "language": self.language,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "percentage": round(self.percentage, 2),
        }


@dataclass
class TreeNode:
    """Represents a file or directory node in the repository tree."""
    name: str
    path: str
    is_dir: bool
    size_bytes: int = 0
    depth: int = 0
    file_count: int = 0
    language: Optional[str] = None
    children: List[TreeNode] = field(default_factory=list)
    truncated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "is_dir": self.is_dir,
            "size_bytes": self.size_bytes,
            "depth": self.depth,
            "file_count": self.file_count,
            "language": self.language,
            "truncated": self.truncated,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass
class RepoMapResult:
    """Encapsulates the complete repository intelligence output."""
    root_path: str
    total_files: int
    total_dirs: int
    total_bytes: int
    languages: List[LanguageStats]
    tree: TreeNode
    entries_shown: int
    total_entries_scanned: int
    truncated: bool
    max_depth_reached: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert result into serializable dictionary."""
        return {
            "root_path": self.root_path,
            "total_files": self.total_files,
            "total_dirs": self.total_dirs,
            "total_bytes": self.total_bytes,
            "total_bytes_formatted": format_size(self.total_bytes),
            "primary_language": self.languages[0].language if self.languages else "Unknown",
            "languages": [lang.to_dict() for lang in self.languages],
            "entries_shown": self.entries_shown,
            "total_entries_scanned": self.total_entries_scanned,
            "truncated": self.truncated,
            "max_depth_reached": self.max_depth_reached,
            "tree": self.tree.to_dict(),
        }

    def to_compact_tree(self, use_unicode: bool = True, show_sizes: bool = True) -> str:
        """Render a compact visual tree hierarchy."""
        lines: List[str] = []
        root_name = self.tree.name or Path(self.root_path).name or "."
        lines.append(f"{root_name}/")

        branch = "├── " if use_unicode else "|-- "
        last_branch = "└── " if use_unicode else "\\-- "
        pipe = "│   " if use_unicode else "|   "
        space = "    "

        def _render_children(children: List[TreeNode], prefix: str = "") -> None:
            count = len(children)
            for idx, child in enumerate(children):
                is_last = (idx == count - 1)
                connector = last_branch if is_last else branch
                extension = space if is_last else pipe

                if child.is_dir:
                    dir_info = f" ({child.file_count} files)" if child.file_count > 0 else ""
                    lines.append(f"{prefix}{connector}{child.name}/{dir_info}")
                    if child.children:
                        _render_children(child.children, prefix + extension)
                else:
                    size_info = f" ({format_size(child.size_bytes)})" if show_sizes else ""
                    lang_info = f" [{child.language}]" if child.language else ""
                    lines.append(f"{prefix}{connector}{child.name}{size_info}{lang_info}")

        if self.tree.children:
            _render_children(self.tree.children)

        if self.truncated:
            lines.append(
                f"\n[... Output bounded: {self.entries_shown} entries shown out of "
                f"{self.total_entries_scanned} scanned items]"
            )

        return "\n".join(lines)

    def to_markdown_summary(self) -> str:
        """Render a markdown summary including language breakdown and compact tree."""
        primary = self.languages[0].language if self.languages else "None"
        primary_pct = f"{self.languages[0].percentage:.1f}%" if self.languages else "0%"
        size_str = format_size(self.total_bytes)

        md = [
            f"### Repository Map: `{self.tree.name or Path(self.root_path).name}`",
            f"- **Overview:** {self.total_files} files in {self.total_dirs} directories ({size_str})",
            f"- **Primary Language:** {primary} ({primary_pct})",
            f"- **Entries Displayed:** {self.entries_shown} (Truncated: {'Yes' if self.truncated else 'No'})",
            "",
            "#### Language Distribution",
            "| Language | Files | Size | Share |",
            "| :--- | :--- | :--- | :--- |",
        ]

        for lang in self.languages[:8]:
            md.append(
                f"| **{lang.language}** | {lang.file_count} | {format_size(lang.total_bytes)} | {lang.percentage:.1f}% |"
            )

        md.extend([
            "",
            "#### Directory Hierarchy",
            "```text",
            self.to_compact_tree(),
            "```",
        ])

        return "\n".join(md)


# ==============================================================================
# 4. GITIGNORE & EXCLUSION PARSER
# ==============================================================================

class ExclusionFilter:
    """Evaluates whether paths and directory names should be excluded."""

    def __init__(
        self,
        root_path: Path,
        custom_patterns: Optional[List[str]] = None,
        respect_gitignore: bool = True,
    ) -> None:
        self.root_path = root_path
        self.custom_patterns = list(custom_patterns or [])
        self.gitignore_patterns: List[str] = []

        if respect_gitignore:
            self._load_gitignore()

    def _load_gitignore(self) -> None:
        gitignore_path = self.root_path / ".gitignore"
        if not gitignore_path.is_file():
            return

        try:
            with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    # Normalize pattern
                    if line.startswith("/"):
                        line = line[1:]
                    self.gitignore_patterns.append(line)
        except OSError:
            pass

    def is_excluded_dir(self, dir_name: str, rel_path: str) -> bool:
        """Check if a directory should be pruned before recursion."""
        if dir_name in DEFAULT_EXCLUDED_DIRS:
            return True

        norm_rel = rel_path.replace("\\", "/").rstrip("/")

        for pat in DEFAULT_EXCLUDED_PATTERNS + self.custom_patterns:
            if fnmatch.fnmatch(dir_name, pat) or fnmatch.fnmatch(norm_rel, pat):
                return True

        for pat in self.gitignore_patterns:
            clean_pat = pat.rstrip("/")
            if fnmatch.fnmatch(dir_name, clean_pat) or fnmatch.fnmatch(norm_rel, clean_pat):
                return True
            if fnmatch.fnmatch(f"{norm_rel}/", pat):
                return True

        return False

    def is_excluded_file(self, file_name: str, rel_path: str) -> bool:
        """Check if a file should be excluded."""
        norm_rel = rel_path.replace("\\", "/").lstrip("./")

        for pat in DEFAULT_EXCLUDED_PATTERNS + self.custom_patterns:
            if fnmatch.fnmatch(file_name, pat) or fnmatch.fnmatch(norm_rel, pat):
                return True

        for pat in self.gitignore_patterns:
            clean_pat = pat.rstrip("/")
            if fnmatch.fnmatch(file_name, clean_pat) or fnmatch.fnmatch(norm_rel, clean_pat):
                return True

        return False


# ==============================================================================
# 5. REPOSITORY SCANNER & INTELLIGENCE GENERATOR
# ==============================================================================

class RepoMapScanner:
    """High-performance repository scanner using os.scandir with bounding constraints."""

    def __init__(
        self,
        root_path: Union[str, Path],
        max_depth: int = 4,
        max_entries: int = 150,
        exclude_patterns: Optional[List[str]] = None,
        respect_gitignore: bool = True,
    ) -> None:
        self.root = Path(root_path).resolve()
        if not self.root.exists():
            raise FileNotFoundError(f"Path does not exist: {self.root}")
        if not self.root.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {self.root}")

        self.max_depth = max(1, max_depth)
        self.max_entries = max(1, max_entries)
        self.filter = ExclusionFilter(
            self.root,
            custom_patterns=exclude_patterns,
            respect_gitignore=respect_gitignore,
        )

        # Global counters & state
        self.entries_shown = 0
        self.total_scanned = 0
        self.total_files = 0
        self.total_dirs = 0
        self.total_bytes = 0
        self.truncated = False
        self.max_depth_reached = False
        self.language_counts: Dict[str, int] = {}
        self.language_bytes: Dict[str, int] = {}
        self.visited_inodes: Set[int] = set()

    def scan(self) -> RepoMapResult:
        """Execute scan and construct bounded repository map."""
        root_name = self.root.name or "."
        root_node = TreeNode(
            name=root_name,
            path="",
            is_dir=True,
            depth=0,
        )

        self._scan_directory(self.root, root_node, depth=1)

        # Calculate language statistics
        lang_stats: List[LanguageStats] = []
        for lang, count in self.language_counts.items():
            bytes_count = self.language_bytes.get(lang, 0)
            pct = (count / self.total_files * 100.0) if self.total_files > 0 else 0.0
            lang_stats.append(
                LanguageStats(
                    language=lang,
                    file_count=count,
                    total_bytes=bytes_count,
                    percentage=pct,
                )
            )

        # Sort languages by file count descending, then by bytes
        lang_stats.sort(key=lambda s: (s.file_count, s.total_bytes), reverse=True)

        return RepoMapResult(
            root_path=str(self.root),
            total_files=self.total_files,
            total_dirs=self.total_dirs,
            total_bytes=self.total_bytes,
            languages=lang_stats,
            tree=root_node,
            entries_shown=self.entries_shown,
            total_entries_scanned=self.total_scanned,
            truncated=self.truncated,
            max_depth_reached=self.max_depth_reached,
        )

    def _scan_directory(self, current_path: Path, current_node: TreeNode, depth: int) -> None:
        """Recursively scan a directory, populating nodes up to max_depth and max_entries."""
        if depth > self.max_depth:
            self.max_depth_reached = True
            return

        try:
            stat_info = current_path.stat()
            if hasattr(stat_info, "st_ino") and stat_info.st_ino != 0:
                if stat_info.st_ino in self.visited_inodes:
                    return
                self.visited_inodes.add(stat_info.st_ino)
        except OSError:
            pass

        try:
            with os.scandir(current_path) as it:
                raw_entries = list(it)
        except (PermissionError, OSError):
            return

        # Segregate and sort deterministically: directories first (case-insensitive), then files
        dirs_list: List[os.DirEntry] = []
        files_list: List[os.DirEntry] = []

        for entry in raw_entries:
            try:
                rel_path = (
                    Path(entry.path).relative_to(self.root).as_posix()
                )
            except ValueError:
                rel_path = entry.name

            try:
                if entry.is_dir(follow_symlinks=False):
                    if not self.filter.is_excluded_dir(entry.name, rel_path):
                        dirs_list.append(entry)
                elif entry.is_file(follow_symlinks=False):
                    if not self.filter.is_excluded_file(entry.name, rel_path):
                        files_list.append(entry)
            except OSError:
                continue

        dirs_list.sort(key=lambda e: e.name.lower())
        files_list.sort(key=lambda e: e.name.lower())

        # Process directories
        for d_entry in dirs_list:
            self.total_scanned += 1
            self.total_dirs += 1

            rel_path = Path(d_entry.path).relative_to(self.root).as_posix()
            can_display = self.entries_shown < self.max_entries

            child_node = TreeNode(
                name=d_entry.name,
                path=rel_path,
                is_dir=True,
                depth=depth,
            )

            if can_display:
                self.entries_shown += 1
                current_node.children.append(child_node)
            else:
                self.truncated = True

            # Recurse down
            dir_path = Path(d_entry.path)
            self._scan_directory(dir_path, child_node, depth=depth + 1)
            current_node.file_count += child_node.file_count

        # Process files
        for f_entry in files_list:
            self.total_scanned += 1
            self.total_files += 1
            current_node.file_count += 1

            size = 0
            try:
                size = f_entry.stat().st_size
            except OSError:
                pass

            self.total_bytes += size
            lang = detect_language(f_entry.name)
            if lang:
                self.language_counts[lang] = self.language_counts.get(lang, 0) + 1
                self.language_bytes[lang] = self.language_bytes.get(lang, 0) + size

            can_display = self.entries_shown < self.max_entries
            if can_display:
                self.entries_shown += 1
                rel_path = Path(f_entry.path).relative_to(self.root).as_posix()
                file_node = TreeNode(
                    name=f_entry.name,
                    path=rel_path,
                    is_dir=False,
                    size_bytes=size,
                    depth=depth,
                    language=lang,
                )
                current_node.children.append(file_node)
            else:
                self.truncated = True


# ==============================================================================
# 6. PUBLIC API FUNCTION
# ==============================================================================

def generate_repo_map(
    root_path: Union[str, Path] = ".",
    max_depth: int = 4,
    max_entries: int = 150,
    exclude_patterns: Optional[List[str]] = None,
    respect_gitignore: bool = True,
    show_sizes: bool = True,
    as_format: str = "text",
) -> Union[str, Dict[str, Any], RepoMapResult]:
    """Generate a compact repository structure, language breakdown, and directory tree.

    Args:
        root_path: Directory root to analyze.
        max_depth: Maximum directory traversal depth (default 4).
        max_entries: Maximum entries in tree view before bounding (default 150).
        exclude_patterns: Additional file or folder patterns to exclude.
        respect_gitignore: Whether to load root .gitignore if present (default True).
        show_sizes: Show formatted byte sizes in tree text (default True).
        as_format: Format of the return value: 'text' (default), 'markdown', 'dict', or 'object'.

    Returns:
        Formatted string, dictionary, or RepoMapResult instance according to as_format.
    """
    scanner = RepoMapScanner(
        root_path=root_path,
        max_depth=max_depth,
        max_entries=max_entries,
        exclude_patterns=exclude_patterns,
        respect_gitignore=respect_gitignore,
    )
    result = scanner.scan()

    if as_format == "text":
        return result.to_compact_tree(show_sizes=show_sizes)
    elif as_format == "markdown":
        return result.to_markdown_summary()
    elif as_format == "dict":
        return result.to_dict()
    elif as_format == "object":
        return result
    else:
        raise ValueError(f"Unknown format '{as_format}'. Supported: 'text', 'markdown', 'dict', 'object'.")


# ==============================================================================
# 7. STANDALONE CLI ENTRYPOINT
# ==============================================================================

if __name__ == "__main__":
    import argparse
    import json
    import sys

    # Reconfigure stdout/stderr on Windows to handle unicode cleanly
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="OmniTools Repository Intelligence & Map Generator")
    parser.add_argument("path", nargs="?", default=".", help="Root path of repository (default: current directory)")
    parser.add_argument("--max-depth", type=int, default=4, help="Max recursion depth (default: 4)")
    parser.add_argument("--max-entries", type=int, default=150, help="Max entries in tree (default: 150)")
    parser.add_argument("--format", choices=["text", "markdown", "dict"], default="text", help="Output format")
    parser.add_argument("--no-sizes", action="store_true", help="Omit file sizes from tree")
    parser.add_argument("--no-gitignore", action="store_true", help="Do not respect .gitignore")
    parser.add_argument("--ascii", action="store_true", help="Use pure ASCII tree characters")

    args = parser.parse_args()

    try:
        if args.format == "text" and args.ascii:
            res = generate_repo_map(
                root_path=args.path,
                max_depth=args.max_depth,
                max_entries=args.max_entries,
                respect_gitignore=not args.no_gitignore,
                show_sizes=not args.no_sizes,
                as_format="object",
            )
            print(res.to_compact_tree(use_unicode=False, show_sizes=not args.no_sizes))
        else:
            output = generate_repo_map(
                root_path=args.path,
                max_depth=args.max_depth,
                max_entries=args.max_entries,
                respect_gitignore=not args.no_gitignore,
                show_sizes=not args.no_sizes,
                as_format=args.format,
            )

            if args.format == "dict":
                print(json.dumps(output, indent=2))
            else:
                print(output)
    except Exception as exc:
        print(f"Error generating repo map: {exc}", file=sys.stderr)
        sys.exit(1)
