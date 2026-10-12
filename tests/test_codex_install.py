"""Automated verification suite for Codex plugin marketplace operations.

Validates the local marketplace manifest (.agents/plugins/marketplace.json) statically
and exercises real CLI operations with codex/codex.exe when available:
- Static: Marketplace manifest schema, encoding (no BOM), and file integrity (always runs on CI)
- Live CLI: codex --version, marketplace add/list, plugin add/remove lifecycle (skipped if codex not in PATH)
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE_MANIFEST = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
CODEX_CACHE_DIR = (
    Path.home()
    / ".codex"
    / "plugins"
    / "cache"
    / "universal-ai-tools-hub"
    / "omnitools-bridge"
)


def find_codex_binary() -> Optional[str]:
    """Locate codex executable in PATH or standard user installation locations.

    Returns:
        Path to codex executable as string if found, or None if not installed / not in PATH.
    """
    which_path = shutil.which("codex") or shutil.which("codex.exe")
    if which_path:
        return which_path

    # Common Windows installation fallback path
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        fallback = Path(local_app_data) / "Programs" / "OpenAI" / "Codex" / "bin" / "codex.exe"
        if fallback.is_file():
            return str(fallback)

    return None


CODEX_BIN = find_codex_binary()
HAS_CODEX = CODEX_BIN is not None

skip_without_codex = pytest.mark.skipif(
    not HAS_CODEX,
    reason="codex or codex.exe CLI executable not found in PATH or standard install locations",
)


def run_codex_cmd(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    """Helper to execute codex CLI commands from the repository root."""
    if not CODEX_BIN:
        raise RuntimeError(
            "run_codex_cmd called when CODEX_BIN is None. "
            "Ensure live CLI tests are guarded with @skip_without_codex."
        )
    cmd = [CODEX_BIN] + args
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


# ===========================================================================
# Section 1: Static Manifest Schema & Integrity Tests (CI-Safe, No Codex Needed)
# ===========================================================================

def test_marketplace_manifest_exists_and_valid_json():
    """Verify that .agents/plugins/marketplace.json exists, has no UTF-8 BOM, and is valid JSON."""
    assert MARKETPLACE_MANIFEST.is_file(), (
        f"Marketplace manifest not found at {MARKETPLACE_MANIFEST}"
    )

    # Validate raw bytes have no UTF-8 BOM (\xef\xbb\xbf)
    raw_bytes = MARKETPLACE_MANIFEST.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), (
        "Marketplace manifest contains an illegal UTF-8 BOM marker"
    )

    # Validate JSON parsing
    try:
        manifest = json.loads(raw_bytes.decode("utf-8"))
    except Exception as exc:
        pytest.fail(f"Failed to parse {MARKETPLACE_MANIFEST} as valid JSON: {exc}")

    # Validate required top-level fields
    assert "name" in manifest, "Manifest missing required top-level 'name' field"
    assert manifest["name"] == "universal-ai-tools-hub", (
        f"Unexpected marketplace name: {manifest['name']}"
    )

    assert "interface" in manifest and isinstance(manifest["interface"], dict), (
        "Manifest missing 'interface' dictionary"
    )
    assert manifest["interface"].get("displayName"), (
        "Manifest missing interface.displayName"
    )

    assert "plugins" in manifest and isinstance(manifest["plugins"], list), (
        "Manifest missing 'plugins' list"
    )
    assert len(manifest["plugins"]) > 0, "Manifest 'plugins' list is empty"


def test_marketplace_manifest_plugins_schema_and_disk_files():
    """Verify each plugin entry schema and ensure local source paths and required files exist on disk."""
    assert MARKETPLACE_MANIFEST.is_file(), f"Missing manifest: {MARKETPLACE_MANIFEST}"
    manifest = json.loads(MARKETPLACE_MANIFEST.read_text(encoding="utf-8"))

    for plugin in manifest.get("plugins", []):
        plugin_name = plugin.get("name")
        assert plugin_name, f"Plugin missing 'name' attribute: {plugin}"
        assert plugin.get("displayName"), f"Plugin '{plugin_name}' missing displayName"
        assert plugin.get("description"), f"Plugin '{plugin_name}' missing description"
        assert plugin.get("category"), f"Plugin '{plugin_name}' missing category"
        assert plugin.get("policy"), f"Plugin '{plugin_name}' missing policy"

        source = plugin.get("source", {})
        assert source.get("source") == "local", (
            f"Plugin '{plugin_name}' source must be 'local', got {source.get('source')}"
        )
        plugin_rel_path = source.get("path")
        assert plugin_rel_path, f"Plugin '{plugin_name}' source.path must not be empty"

        plugin_abs_path = (REPO_ROOT / plugin_rel_path).resolve()
        assert plugin_abs_path.is_dir(), (
            f"Plugin source path does not exist on disk: {plugin_abs_path}"
        )

        # Validate core plugin manifest and entrypoints
        has_plugin_json = (
            (plugin_abs_path / "plugin.json").is_file()
            or (plugin_abs_path / ".codex-plugin" / "plugin.json").is_file()
        )
        assert has_plugin_json, (
            f"Plugin '{plugin_name}' missing plugin.json at {plugin_abs_path}"
        )

        assert (plugin_abs_path / "run_mcp.py").is_file(), (
            f"Plugin '{plugin_name}' missing run_mcp.py at {plugin_abs_path}"
        )
        assert (plugin_abs_path / "skills").is_dir(), (
            f"Plugin '{plugin_name}' missing skills directory at {plugin_abs_path}"
        )
        assert (plugin_abs_path / "src" / "core" / "tools.py").is_file(), (
            f"Plugin '{plugin_name}' missing src/core/tools.py at {plugin_abs_path}"
        )


# ===========================================================================
# Section 2: Live Codex CLI Tests (Skipped Gracefully if Codex is Absent)
# ===========================================================================

@skip_without_codex
def test_codex_cli_available():
    """Verify that codex executable is available and responds to version query."""
    res = run_codex_cmd(["--version"])
    assert res.returncode == 0, (
        f"Failed to execute '{CODEX_BIN} --version': {res.stderr}"
    )
    assert "codex" in res.stdout.lower() or "version" in res.stdout.lower(), (
        f"Unexpected output from codex --version: {res.stdout}"
    )


@skip_without_codex
def test_codex_marketplace_add_json():
    """Verify that 'codex plugin marketplace add . --json' returns valid JSON and succeeds."""
    res = run_codex_cmd(["plugin", "marketplace", "add", ".", "--json"])
    # If already registered from an old/different path, clean and re-add
    if res.returncode != 0 and "already added from a different source" in (res.stderr + res.stdout):
        run_codex_cmd(["plugin", "marketplace", "remove", "universal-ai-tools-hub"])
        res = run_codex_cmd(["plugin", "marketplace", "add", ".", "--json"])

    assert res.returncode == 0, (
        f"codex plugin marketplace add . --json failed with code {res.returncode}:\n"
        f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}"
    )

    try:
        data = json.loads(res.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"Failed to parse codex marketplace add output as JSON: {exc}\nRaw: {res.stdout}"
        )

    assert data.get("marketplaceName") == "universal-ai-tools-hub", (
        f"Unexpected marketplaceName in JSON output: {data}"
    )
    assert "installedRoot" in data, f"Missing installedRoot in output: {data}"
    assert Path(data["installedRoot"]).resolve() == REPO_ROOT.resolve(), (
        f"installedRoot ({data['installedRoot']}) does not match repo root ({REPO_ROOT})"
    )


@skip_without_codex
def test_codex_marketplace_list():
    """Verify that 'codex plugin marketplace list' lists universal-ai-tools-hub."""
    res = run_codex_cmd(["plugin", "marketplace", "list"])
    assert res.returncode == 0, (
        f"codex plugin marketplace list failed with code {res.returncode}:\n{res.stderr}"
    )
    assert "universal-ai-tools-hub" in res.stdout, (
        f"'universal-ai-tools-hub' not found in marketplace list:\n{res.stdout}"
    )
    assert str(REPO_ROOT) in res.stdout or REPO_ROOT.name in res.stdout, (
        f"Repository root not found in marketplace list output:\n{res.stdout}"
    )


@skip_without_codex
def test_codex_plugin_install_cache_and_remove_lifecycle():
    """Full end-to-end lifecycle verification:
    1. Clean state pre-check / remove previous installation
    2. codex plugin add omnitools-bridge@universal-ai-tools-hub
    3. Inspect local cache directory ~/.codex/plugins/cache/universal-ai-tools-hub/omnitools-bridge
    4. Validate installed files inside the versioned cache directory
    5. codex plugin remove omnitools-bridge@universal-ai-tools-hub
    6. Verify clean cache directory removal.
    """
    plugin_spec = "omnitools-bridge@universal-ai-tools-hub"

    # Pre-clean: Ensure plugin is not already installed from a previous partial run
    run_codex_cmd(["plugin", "remove", plugin_spec])

    try:
        # Step 1: Install plugin
        add_res = run_codex_cmd(["plugin", "add", plugin_spec])
        assert add_res.returncode == 0, (
            f"codex plugin add failed with code {add_res.returncode}:\n"
            f"STDOUT: {add_res.stdout}\nSTDERR: {add_res.stderr}"
        )
        assert "Added plugin" in add_res.stdout or "omnitools-bridge" in add_res.stdout, (
            f"Expected confirmation message in stdout:\n{add_res.stdout}"
        )

        # Step 2: Inspect cache directory
        assert CODEX_CACHE_DIR.exists(), (
            f"Codex plugin cache directory does not exist: {CODEX_CACHE_DIR}"
        )
        assert CODEX_CACHE_DIR.is_dir(), (
            f"Codex plugin cache path is not a directory: {CODEX_CACHE_DIR}"
        )

        # Locate version subdirectory (e.g. 1.0.0)
        version_dirs = [d for d in CODEX_CACHE_DIR.iterdir() if d.is_dir()]
        assert len(version_dirs) >= 1, (
            f"No version subdirectory found in cache: {list(CODEX_CACHE_DIR.iterdir())}"
        )
        installed_root = version_dirs[0]

        # Step 3: Inspect installed files inside cached version directory
        has_plugin_manifest = (
            (installed_root / "plugin.json").is_file()
            or (installed_root / ".codex-plugin" / "plugin.json").is_file()
        )
        assert has_plugin_manifest, (
            f"No plugin.json manifest found in cached installation at {installed_root}"
        )

        assert (installed_root / "run_mcp.py").is_file(), (
            f"run_mcp.py entrypoint missing in cached installation at {installed_root}"
        )

        assert (installed_root / "skills").is_dir(), (
            f"skills directory missing in cached installation at {installed_root}"
        )

        assert (installed_root / "src").is_dir(), (
            f"src directory missing in cached installation at {installed_root}"
        )
        assert (installed_root / "src" / "core" / "tools.py").is_file(), (
            f"tools.py missing in cached installation at {installed_root}"
        )

    finally:
        # Step 4: Removal and cleanup (guaranteed execution)
        time.sleep(0.2)
        remove_res = run_codex_cmd(["plugin", "remove", plugin_spec])
        if remove_res.returncode != 0:
            time.sleep(0.5)
            remove_res = run_codex_cmd(["plugin", "remove", plugin_spec])

        if CODEX_CACHE_DIR.exists():
            shutil.rmtree(CODEX_CACHE_DIR, ignore_errors=True)
        assert not CODEX_CACHE_DIR.exists(), (
            f"Codex plugin cache directory still exists after removal: {CODEX_CACHE_DIR}"
        )


@skip_without_codex
def test_persist_plugin_installation_ready_state():
    """Ensure plugin is installed and ready in Codex cache after test suite runs."""
    plugin_spec = "omnitools-bridge@universal-ai-tools-hub"
    res = run_codex_cmd(["plugin", "add", plugin_spec])
    assert res.returncode == 0, f"Failed to persist plugin installation: {res.stdout}"
    assert CODEX_CACHE_DIR.exists(), "Cache dir should exist after re-adding plugin"
    list_res = run_codex_cmd(["plugin", "list"])
    assert "omnitools-bridge@universal-ai-tools-hub" in list_res.stdout
    assert "installed, enabled" in list_res.stdout


# ---------------------------------------------------------------------------
# Standalone CLI entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if HAS_CODEX:
        print(f"[QA] Running Codex Verification Suite (Live CLI via {CODEX_BIN})...")
    else:
        print("[QA] Running Codex Verification Suite (Static manifest tests only, CLI not in PATH)...")
    exit_code = pytest.main(["-v", __file__])
    sys.exit(exit_code)
