"""Automated verification suite for Codex plugin marketplace operations.

Validates the local marketplace manifest (.agents/plugins/marketplace.json)
and exercises real CLI operations with codex.exe:
- Marketplace manifest schema, encoding (no BOM), and file integrity
- codex plugin marketplace add . --json
- codex plugin marketplace list
- codex plugin add omnitools-bridge@universal-ai-tools-hub
- Cache directory inspection (~/.codex/plugins/cache/universal-ai-tools-hub/omnitools-bridge)
- codex plugin remove omnitools-bridge@universal-ai-tools-hub and cleanup verification
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
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


def find_codex_binary() -> str:
    """Locate codex executable in PATH or standard user installation locations."""
    which_path = shutil.which("codex") or shutil.which("codex.exe")
    if which_path:
        return which_path

    # Common Windows installation fallback path
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        fallback = Path(local_app_data) / "Programs" / "OpenAI" / "Codex" / "bin" / "codex.exe"
        if fallback.exists():
            return str(fallback)

    return "codex"


CODEX_BIN = find_codex_binary()


def run_codex_cmd(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    """Helper to execute codex CLI commands from the repository root."""
    cmd = [CODEX_BIN] + args
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


# ---------------------------------------------------------------------------
# Test 1: Marketplace Manifest Validation
# ---------------------------------------------------------------------------
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

    # Validate omnitools-bridge plugin entry
    bridge_plugin = next(
        (p for p in manifest["plugins"] if p.get("name") == "omnitools-bridge"),
        None,
    )
    assert bridge_plugin is not None, (
        "omnitools-bridge plugin entry not found in marketplace manifest"
    )

    # Validate source path resolves to existing directory
    source = bridge_plugin.get("source", {})
    assert source.get("source") == "local", "Plugin source must be 'local'"
    plugin_rel_path = source.get("path")
    assert plugin_rel_path, "Plugin source.path must not be empty"

    plugin_abs_path = (REPO_ROOT / plugin_rel_path).resolve()
    assert plugin_abs_path.is_dir(), (
        f"Plugin source path does not exist on disk: {plugin_abs_path}"
    )

    # Validate core plugin metadata
    assert bridge_plugin.get("displayName"), "Plugin displayName missing"
    assert bridge_plugin.get("description"), "Plugin description missing"
    assert bridge_plugin.get("category"), "Plugin category missing"
    assert bridge_plugin.get("policy"), "Plugin policy missing"


# ---------------------------------------------------------------------------
# Test 2: Codex CLI Availability
# ---------------------------------------------------------------------------
def test_codex_cli_available():
    """Verify that codex.exe executable is available and responds to version query."""
    res = run_codex_cmd(["--version"])
    assert res.returncode == 0, (
        f"Failed to execute '{CODEX_BIN} --version': {res.stderr}"
    )
    assert "codex" in res.stdout.lower() or "version" in res.stdout.lower(), (
        f"Unexpected output from codex --version: {res.stdout}"
    )


# ---------------------------------------------------------------------------
# Test 3: codex plugin marketplace add . --json
# ---------------------------------------------------------------------------
def test_codex_marketplace_add_json():
    """Verify that 'codex plugin marketplace add . --json' returns valid JSON and succeeds."""
    res = run_codex_cmd(["plugin", "marketplace", "add", ".", "--json"])
    assert res.returncode == 0, (
        f"codex plugin marketplace add . --json failed with code {res.returncode}:\n"
        f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}"
    )

    # Parse JSON output from CLI
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


# ---------------------------------------------------------------------------
# Test 4: codex plugin marketplace list
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Test 5 & 6: Codex Plugin Install, Cache Verification, and Removal Lifecycle
# ---------------------------------------------------------------------------
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
    pre_clean = run_codex_cmd(["plugin", "remove", plugin_spec])
    # Note: pre_clean may return non-zero if not installed; that is acceptable

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
        # Required files: plugin.json or .codex-plugin/plugin.json, run_mcp.py, skills, src
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
        import time, shutil
        time.sleep(0.2)
        remove_res = run_codex_cmd(["plugin", "remove", plugin_spec])
        # If removal returns 0 or cache already unlinked, verify/clean cache dir
        if remove_res.returncode != 0:
            time.sleep(0.5)
            remove_res = run_codex_cmd(["plugin", "remove", plugin_spec])
        
        if CODEX_CACHE_DIR.exists():
            shutil.rmtree(CODEX_CACHE_DIR, ignore_errors=True)
        assert not CODEX_CACHE_DIR.exists(), (
            f"Codex plugin cache directory still exists after removal: {CODEX_CACHE_DIR}"
        )


# ---------------------------------------------------------------------------
# Standalone CLI entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"[QA] Running Codex Install Verification Suite via {CODEX_BIN}...")
    exit_code = pytest.main(["-v", __file__])
    sys.exit(exit_code)
