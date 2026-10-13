"""Real stdio MCP calls against a disposable, process-authorized Git repo."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ADAPTER = Path(__file__).resolve().parents[1] / "src" / "adapters" / "mcp_adapter.py"
CODING_TOOLS = (
    "repo_map", "search_code", "read_symbol", "find_references",
    "dependency_graph", "propose_patch", "apply_patch", "run_targeted_tests",
    "verify_changes", "summarize_context", "estimate_tokens", "git_checkpoint",
    "diagnose_error", "find_documentation", "search_coding_catalog",
)


def _exchange(workspace: Path, calls: list[tuple[str, dict]]) -> list[dict]:
    env = os.environ.copy()
    env["OMNITOOLS_AUTHORIZED_ROOTS"] = str(workspace)
    env["PYTHONPATH"] = str(ADAPTER.parents[2])
    requests = [
        {"jsonrpc": "2.0", "id": index, "method": "tools/call",
         "params": {"name": name, "arguments": arguments}}
        for index, (name, arguments) in enumerate(calls, 1)
    ]
    process = subprocess.Popen(
        [sys.executable, str(ADAPTER)], cwd=workspace, env=env,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8",
    )
    try:
        stdout, stderr = process.communicate(
            "".join(json.dumps(request) + "\n" for request in requests), timeout=45,
        )
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        pytest.fail("MCP subprocess did not answer and exit after EOF")
    assert process.returncode == 0, stderr
    responses = [json.loads(line) for line in stdout.splitlines()]
    assert [response.get("id") for response in responses] == list(range(1, len(calls) + 1)), stderr
    return responses


def _payload(response: dict) -> dict:
    assert "result" in response, response
    return json.loads(response["result"]["content"][0]["text"])


@pytest.fixture
def synthetic_repo(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "module.py").write_text(
        "import json\n\ndef sample(value):\n    return json.dumps(value)\n\nanswer = sample(42)\n",
        encoding="utf-8",
    )
    (workspace / "test_sample.py").write_text(
        "from module import sample\n\ndef test_sample():\n    assert sample(42) == '42'\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
    subprocess.run(["git", "config", "--local", "user.name", "Synthetic Test"], cwd=workspace, check=True)
    subprocess.run(["git", "config", "--local", "user.email", "test@example.invalid"], cwd=workspace, check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-qm", "Initial synthetic commit"], cwd=workspace, check=True)
    return workspace


def test_all_15_coding_tools_over_stdio(synthetic_repo: Path):
    root = synthetic_repo
    module = str(root / "module.py")
    test_file = str(root / "test_sample.py")
    calls = [
        ("repo_map", {"root_path": str(root)}),
        ("search_code", {"pattern": "sample", "path": str(root)}),
        ("read_symbol", {"file_path": module, "symbol_name": "sample"}),
        ("find_references", {"symbol_name": "sample", "workspace_root": str(root)}),
        ("dependency_graph", {"file_path": module}),
        ("propose_patch", {"file_path": module, "new_content": (root / "module.py").read_text(encoding="utf-8")}),
        ("apply_patch", {"file_path": module, "new_content": (root / "module.py").read_text(encoding="utf-8") + "\n# synthetic patch\n", "confirm": True}),
        ("run_targeted_tests", {"targets": [test_file], "pytest_args": ["-q"]}),
        ("verify_changes", {"changed_files": [module], "test_targets": [test_file]}),
        ("summarize_context", {"source": module}),
        ("estimate_tokens", {"text": "synthetic context"}),
        ("git_checkpoint", {"action": "create", "name": "synthetic"}),
        ("diagnose_error", {"error_traceback": "ValueError: synthetic"}),
        ("find_documentation", {"query": "json.dumps", "library": "json"}),
        ("search_coding_catalog", {"query": "python"}),
    ]
    responses = _exchange(root, calls)
    assert len(responses) == len(CODING_TOOLS)
    for (name, _), response in zip(calls, responses):
        payload = _payload(response)
        assert not (isinstance(payload, dict) and payload.get("ok") is False), (name, payload)
        assert not (isinstance(payload, dict) and payload.get("status") == "error"), (name, payload)
    assert "# synthetic patch" in (root / "module.py").read_text(encoding="utf-8")
    assert _payload(responses[7])["success"] is True
    assert _payload(responses[8])["passed"] is True
    assert _payload(responses[10])["tokens"] > 0
    assert _payload(responses[11])["status"] == "success"


def test_external_read_and_write_denied_over_stdio(synthetic_repo: Path, tmp_path: Path):
    external = tmp_path / "outside.py"
    external.write_text("secret = 'synthetic'\n", encoding="utf-8")
    calls = [
        ("repo_map", {"root_path": str(tmp_path)}),
        ("read_symbol", {"file_path": str(external), "symbol_name": "secret"}),
        ("estimate_tokens", {"file_paths": [str(external)]}),
        ("apply_patch", {"file_path": str(external), "new_content": "changed\n"}),
        ("run_targeted_tests", {"targets": [str(external)]}),
    ]
    for response in _exchange(synthetic_repo, calls):
        assert _payload(response)["error"]["code"] == "WORKSPACE_ACCESS_DENIED"
    assert external.read_text(encoding="utf-8") == "secret = 'synthetic'\n"
