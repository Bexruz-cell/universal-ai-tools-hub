"""Comprehensive Integration and Functional Test Suite for the 15 Coding Tools.

This suite validates all 15 specialized developer & coding agent tools:
 1. repo_map            - Compact repository tree, language breakdown & bounded structure
 2. search_code         - Fast code search with ripgrep & Python fallback, line bounding
 3. read_symbol         - AST-based function/class symbol extraction with body lines
 4. find_references     - AST & regex reference scanner (definitions, calls, imports)
 5. dependency_graph    - Dependency graph analysis, internal/external deps, affected tests
 6. propose_patch       - Strictly read-only unified diff generation with SHA256 checksums
 7. apply_patch         - Atomic patch application with confirmation, backup & syntax gate
 8. run_targeted_tests  - Pytest execution with process timeout, bounded output & isolation
 9. verify_changes      - Multi-stage verification gate (syntax check, test run & regression)
10. summarize_context   - 4-tier context compressor and outline generator for handoffs
11. estimate_tokens     - Fast multi-script token estimation with ChatML & tiktoken fallback
12. git_checkpoint      - Safe rollback point creation, diff inspection & restoration
13. diagnose_error      - Traceback parsing, root-cause isolation & suggested remediation
14. find_documentation  - Official programming documentation, signatures & stdlib lookup
15. search_coding_catalog - Curated 50-repository coding catalog query & category filter
"""

from __future__ import annotations

import ast
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

# 1. repo_map
from src.coding_tools.repo_map import generate_repo_map
repo_map = generate_repo_map

# 2. search_code
from src.coding_tools.search import search_code

# 3. read_symbol & 4. find_references
from src.coding_tools.symbols import find_references, read_symbol

# 5. dependency_graph
from src.coding_tools.deps import dependency_graph

# 6. propose_patch & 7. apply_patch
from src.coding_tools.patcher import (
    ConfirmationRequiredError,
    PatchApplyResult,
    PatchProposalResult,
    WorkspaceSecurityError,
    apply_patch,
    propose_patch,
)

# 8. run_targeted_tests & 9. verify_changes
from src.coding_tools.test_runner import (
    TestRunResult,
    TestStatus,
    VerificationResult,
    run_targeted_tests,
    verify_changes,
)

# 10. summarize_context
from src.context_optimizer.compressor import ContextSummary, summarize_context

# 11. estimate_tokens
from src.context_optimizer.budget import estimate_tokens, estimate_tokens_detailed

# 12. git_checkpoint
from src.coding_tools.checkpoints import git_checkpoint

# 13. diagnose_error
from src.coding_tools.diagnostics import diagnose_error, parse_traceback

# 14. find_documentation
from src.coding_tools.docs import find_documentation

# 15. search_coding_catalog
from src.coding_tools.catalog import search_coding_catalog


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def temp_coding_workspace(tmp_path: Path):
    """Creates a realistic miniature software workspace with Python modules, tests, and configs."""
    ws = tmp_path / "mock_project"
    ws.mkdir(parents=True, exist_ok=True)

    src_dir = ws / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    tests_dir = ws / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    # Core module
    math_mod = src_dir / "math_utils.py"
    math_mod.write_text(
        "\"\"\"Mathematical helper utilities.\"\"\"\n\n"
        "def compute_factorial(n: int) -> int:\n"
        "    \"\"\"Return the factorial of n.\"\"\"\n"
        "    if n < 0:\n"
        "        raise ValueError('n must be non-negative')\n"
        "    if n in (0, 1):\n"
        "        return 1\n"
        "    result = 1\n"
        "    for i in range(2, n + 1):\n"
        "        result *= i\n"
        "    return result\n\n\n"
        "class StatsEngine:\n"
        "    \"\"\"Statistics accumulator.\"\"\"\n\n"
        "    def __init__(self, name: str = 'default'):\n"
        "        self.name = name\n"
        "        self.samples: list[float] = []\n\n"
        "    def add_sample(self, val: float) -> None:\n"
        "        \"\"\"Record a sample value.\"\"\"\n"
        "        self.samples.append(val)\n\n"
        "    def mean(self) -> float:\n"
        "        \"\"\"Compute sample mean.\"\"\"\n"
        "        if not self.samples:\n"
        "            return 0.0\n"
        "        return sum(self.samples) / len(self.samples)\n",
        encoding="utf-8",
    )

    # Consumer module
    consumer_mod = src_dir / "consumer.py"
    consumer_mod.write_text(
        "from src.math_utils import compute_factorial, StatsEngine\n\n"
        "def execute_pipeline():\n"
        "    f5 = compute_factorial(5)\n"
        "    engine = StatsEngine('pipeline')\n"
        "    engine.add_sample(float(f5))\n"
        "    return engine.mean()\n",
        encoding="utf-8",
    )

    # Test module
    test_file = tests_dir / "test_math.py"
    test_file.write_text(
        "from src.math_utils import compute_factorial, StatsEngine\n\n"
        "def test_compute_factorial():\n"
        "    assert compute_factorial(0) == 1\n"
        "    assert compute_factorial(5) == 120\n\n"
        "def test_stats_engine():\n"
        "    se = StatsEngine()\n"
        "    se.add_sample(10.0)\n"
        "    se.add_sample(20.0)\n"
        "    assert se.mean() == 15.0\n",
        encoding="utf-8",
    )

    return ws


# ==============================================================================
# TOOL 1: repo_map
# ==============================================================================

class TestTool01RepoMap:
    def test_repo_map_returns_text_tree(self, temp_coding_workspace: Path):
        tree = repo_map(root_path=temp_coding_workspace, as_format="text")
        assert isinstance(tree, str)
        assert "src" in tree
        assert "math_utils.py" in tree
        assert "tests" in tree
        assert "test_math.py" in tree

    def test_repo_map_markdown_summary(self, temp_coding_workspace: Path):
        md = repo_map(root_path=temp_coding_workspace, as_format="markdown")
        assert isinstance(md, str)
        assert "Repository Structure" in md or "Directory Structure" in md or "Files" in md

    def test_repo_map_dict_structure(self, temp_coding_workspace: Path):
        data = repo_map(root_path=temp_coding_workspace, as_format="dict")
        assert isinstance(data, dict)
        assert "root_path" in data
        assert "tree" in data
        assert data["total_files"] >= 3

    def test_repo_map_depth_filtering(self, temp_coding_workspace: Path):
        # Create a deep file
        deep_dir = temp_coding_workspace / "level1" / "level2" / "level3" / "level4"
        deep_dir.mkdir(parents=True, exist_ok=True)
        (deep_dir / "deep.py").write_text("x = 1\n", encoding="utf-8")

        res_shallow = repo_map(root_path=temp_coding_workspace, max_depth=2, as_format="text")
        assert "deep.py" not in res_shallow


# ==============================================================================
# TOOL 2: search_code
# ==============================================================================

class TestTool02SearchCode:
    def test_search_code_literal_match(self, temp_coding_workspace: Path):
        res = search_code("compute_factorial", path=str(temp_coding_workspace))
        assert res["status"] == "success"
        assert res["total_matches"] >= 2
        files = [m["file"] for m in res["matches"]]
        assert any("math_utils.py" in f for f in files)

    def test_search_code_regex_match(self, temp_coding_workspace: Path):
        res = search_code(r"def\s+test_[a-z_]+", path=str(temp_coding_workspace), regex=True)
        assert res["status"] == "success"
        assert res["total_matches"] >= 2
        for m in res["matches"]:
            assert "def test_" in m["content"]

    def test_search_code_with_pattern_filter(self, temp_coding_workspace: Path):
        res = search_code("def", path=str(temp_coding_workspace), include_patterns=["*.py"])
        assert res["status"] == "success"
        assert res["total_matches"] > 0
        for m in res["matches"]:
            assert m["file"].endswith(".py")

    def test_search_code_max_results_bounding(self, temp_coding_workspace: Path):
        res = search_code("def", path=str(temp_coding_workspace), max_results=2)
        assert res["status"] == "success"
        assert len(res["matches"]) <= 2

    def test_search_code_empty_query(self, temp_coding_workspace: Path):
        res = search_code("", path=str(temp_coding_workspace))
        assert res["total_matches"] == 0
        assert res["matches"] == []


# ==============================================================================
# TOOL 3: read_symbol
# ==============================================================================

class TestTool03ReadSymbol:
    def test_read_symbol_function(self, temp_coding_workspace: Path):
        file_path = temp_coding_workspace / "src" / "math_utils.py"
        res = read_symbol(str(file_path), "compute_factorial")
        assert res["found"] is True
        assert res["name"] == "compute_factorial"
        assert res["kind"] == "function"
        assert "compute_factorial(n: int) -> int" in res["signature"]
        assert "Return the factorial of n." in res["docstring"]
        assert "def compute_factorial" in res["body"]

    def test_read_symbol_class(self, temp_coding_workspace: Path):
        file_path = temp_coding_workspace / "src" / "math_utils.py"
        res = read_symbol(str(file_path), "StatsEngine")
        assert res["found"] is True
        assert res["kind"] == "class"
        assert "class StatsEngine" in res["signature"]
        assert "add_sample" in res["body"]

    def test_read_symbol_method_qualified(self, temp_coding_workspace: Path):
        file_path = temp_coding_workspace / "src" / "math_utils.py"
        res = read_symbol(str(file_path), "StatsEngine.mean")
        assert res["found"] is True
        assert res["kind"] == "method"
        assert "Compute sample mean." in res["docstring"]

    def test_read_symbol_not_found(self, temp_coding_workspace: Path):
        file_path = temp_coding_workspace / "src" / "math_utils.py"
        res = read_symbol(str(file_path), "non_existent_function")
        assert res["found"] is False
        assert "not found" in res["error"].lower()

    def test_read_symbol_missing_file(self):
        res = read_symbol("non_existent_file.py", "any_symbol")
        assert res["found"] is False


# ==============================================================================
# TOOL 4: find_references
# ==============================================================================

class TestTool04FindReferences:
    def test_find_references_across_workspace(self, temp_coding_workspace: Path):
        res = find_references("compute_factorial", workspace_root=str(temp_coding_workspace))
        assert res["total_references"] >= 3
        # Should be defined in math_utils, imported in consumer & test_math
        files = [r["file"] for r in res["references"]]
        assert any("math_utils.py" in f for f in files)
        assert any("consumer.py" in f for f in files)
        assert any("test_math.py" in f for f in files)

    def test_find_references_zero_usages(self, temp_coding_workspace: Path):
        res = find_references("never_used_token_12345", workspace_root=str(temp_coding_workspace))
        assert res["total_references"] == 0
        assert res["references"] == []

    def test_find_references_bounded(self, temp_coding_workspace: Path):
        res = find_references("def", workspace_root=str(temp_coding_workspace), max_results=2)
        assert len(res["references"]) <= 2


# ==============================================================================
# TOOL 5: dependency_graph
# ==============================================================================

class TestTool05DependencyGraph:
    def test_dependency_graph_module(self, temp_coding_workspace: Path):
        target = temp_coding_workspace / "src" / "consumer.py"
        res = dependency_graph(str(target), workspace_root=str(temp_coding_workspace))
        assert "error" not in res
        assert res["file_path"] == "src/consumer.py"
        # Consumer imports math_utils
        assert any("math_utils.py" in str(edge["target"]) for edge in res["edges"])

    def test_dependency_graph_affected_tests(self, temp_coding_workspace: Path):
        target = temp_coding_workspace / "src" / "math_utils.py"
        res = dependency_graph(str(target), workspace_root=str(temp_coding_workspace))
        assert "error" not in res
        assert any("test_math.py" in test for test in res["affected_tests"])

    def test_dependency_graph_nonexistent_file(self, temp_coding_workspace: Path):
        res = dependency_graph("src/missing.py", workspace_root=str(temp_coding_workspace))
        assert "error" in res


# ==============================================================================
# TOOL 6: propose_patch
# ==============================================================================

class TestTool06ProposePatch:
    def test_propose_patch_is_read_only(self, temp_coding_workspace: Path):
        target = temp_coding_workspace / "src" / "math_utils.py"
        original_content = target.read_text(encoding="utf-8")
        modified_content = original_content.replace("return 1", "return 1  # modified")

        proposal = propose_patch(target, new_content=modified_content, workspace_root=temp_coding_workspace)
        assert isinstance(proposal, PatchProposalResult)
        assert proposal.patch_id.startswith("patch-")
        assert proposal.diff != ""
        assert "+    if n in (0, 1):" in proposal.diff or "modified" in proposal.diff

        # Disk content must remain identical!
        assert target.read_text(encoding="utf-8") == original_content

    def test_propose_patch_traversal_rejection(self, temp_coding_workspace: Path):
        with pytest.raises(WorkspaceSecurityError):
            propose_patch("../outside.py", new_content="x = 1\n", workspace_root=temp_coding_workspace)


# ==============================================================================
# TOOL 7: apply_patch
# ==============================================================================

class TestTool07ApplyPatch:
    def test_apply_patch_requires_confirmation(self, temp_coding_workspace: Path):
        target = temp_coding_workspace / "src" / "math_utils.py"
        new_content = target.read_text(encoding="utf-8") + "\n# patch"

        # By default returns unconfirmed result without raising
        res = apply_patch(target, new_content=new_content, workspace_root=temp_coding_workspace, confirm=False)
        assert res.success is False
        assert "confirmation" in res.message.lower()

        # With raise_errors=True it raises
        with pytest.raises(ConfirmationRequiredError):
            apply_patch(target, new_content=new_content, workspace_root=temp_coding_workspace, confirm=False, raise_errors=True)

    def test_apply_patch_success_and_backup(self, temp_coding_workspace: Path):
        target = temp_coding_workspace / "src" / "math_utils.py"
        original = target.read_text(encoding="utf-8")
        patched = original + "\n\ndef is_even(num: int) -> bool:\n    return num % 2 == 0\n"

        res = apply_patch(target, new_content=patched, workspace_root=temp_coding_workspace, confirm=True)
        assert res.success is True
        assert res.syntax_check_passed is True
        assert target.read_text(encoding="utf-8") == patched

        # Verify backup was made
        bak = target.with_suffix(".py.bak")
        assert bak.exists()
        assert bak.read_text(encoding="utf-8") == original

    def test_apply_patch_syntax_error_auto_rollback(self, temp_coding_workspace: Path):
        target = temp_coding_workspace / "src" / "math_utils.py"
        original = target.read_text(encoding="utf-8")
        broken = original + "\n\ndef broken_function(:\n    pass\n"

        res = apply_patch(target, new_content=broken, workspace_root=temp_coding_workspace, confirm=True)
        assert res.success is False
        assert res.syntax_check_passed is False
        assert res.rolled_back is True
        assert res.syntax_error is not None
        # Verify automatic rollback occurred!
        assert target.read_text(encoding="utf-8") == original


# ==============================================================================
# TOOL 8: run_targeted_tests
# ==============================================================================

class TestTool08RunTargetedTests:
    def test_run_targeted_tests_passing(self, temp_coding_workspace: Path):
        res = run_targeted_tests(
            targets=["tests/test_math.py"],
            cwd=temp_coding_workspace,
            timeout_seconds=30.0,
        )
        assert isinstance(res, TestRunResult)
        assert res.status == TestStatus.PASSED
        assert res.passed == 2
        assert res.failed == 0

    def test_run_targeted_tests_failing(self, temp_coding_workspace: Path):
        broken_test = temp_coding_workspace / "tests" / "test_broken.py"
        broken_test.write_text("def test_fail():\n    assert 1 == 2\n", encoding="utf-8")

        res = run_targeted_tests(
            targets=["tests/test_broken.py"],
            cwd=temp_coding_workspace,
            timeout_seconds=30.0,
        )
        assert res.status == TestStatus.FAILED
        assert res.failed == 1
        assert len(res.failures) >= 1
        fail_detail = res.failures[0]
        assert "assert 1 == 2" in fail_detail.error_message or "assert 1 == 2" in fail_detail.traceback_snippet or "1 == 2" in res.stdout


# ==============================================================================
# TOOL 9: verify_changes
# ==============================================================================

class TestTool09VerifyChanges:
    def test_verify_changes_clean(self, temp_coding_workspace: Path):
        changed = ["src/math_utils.py"]
        res = verify_changes(
            changed_files=changed,
            test_targets=["tests/test_math.py"],
            cwd=temp_coding_workspace,
            run_regression=False,
        )
        assert isinstance(res, VerificationResult)
        assert res.passed is True
        assert res.compile_success is True
        assert res.compile_errors == []

    def test_verify_changes_catches_syntax_error(self, temp_coding_workspace: Path):
        broken_file = temp_coding_workspace / "src" / "syntax_err.py"
        broken_file.write_text("def faulty(:\n", encoding="utf-8")

        res = verify_changes(
            changed_files=[broken_file],
            cwd=temp_coding_workspace,
        )
        assert res.passed is False
        assert res.compile_success is False
        assert len(res.compile_errors) >= 1


# ==============================================================================
# TOOL 10: summarize_context
# ==============================================================================

class TestTool10SummarizeContext:
    def test_summarize_context_source_code(self, temp_coding_workspace: Path):
        code = (temp_coding_workspace / "src" / "math_utils.py").read_text(encoding="utf-8")
        summary = summarize_context(code, max_tokens=150)
        assert isinstance(summary, ContextSummary)
        assert summary.stats.symbol_count >= 2
        assert len(summary.symbols) >= 2
        text = str(summary)
        assert "compute_factorial" in text
        assert "StatsEngine" in text

    def test_summarize_context_budget_enforcement(self, temp_coding_workspace: Path):
        code = (temp_coding_workspace / "src" / "math_utils.py").read_text(encoding="utf-8")
        summary_small = summarize_context(code, max_tokens=50)
        summary_large = summarize_context(code, max_tokens=500)
        assert summary_small.stats.compressed_tokens_est <= summary_large.stats.compressed_tokens_est


# ==============================================================================
# TOOL 11: estimate_tokens
# ==============================================================================

class TestTool11EstimateTokens:
    def test_estimate_tokens_string(self):
        text = "def hello():\n    return 'world'\n"
        count = estimate_tokens(text)
        assert count > 0
        assert isinstance(count, int)

    def test_estimate_tokens_empty(self):
        assert estimate_tokens("") == 0

    def test_estimate_tokens_detailed(self):
        res = estimate_tokens_detailed("print('testing 123')", model="gpt-4o")
        assert res.count > 0
        assert res.method is not None

    def test_estimate_tokens_chatml_list(self):
        messages = [
            {"role": "user", "content": "Hello agent!"},
            {"role": "assistant", "content": "I am ready to help."},
        ]
        tokens = estimate_tokens(messages)
        assert tokens > 10


# ==============================================================================
# TOOL 12: git_checkpoint
# ==============================================================================

class TestTool12GitCheckpoint:
    def test_git_checkpoint_lifecycle(self, temp_coding_workspace: Path):
        # Initialize real git repo inside temporary workspace for checkpoint testing
        import subprocess
        subprocess.run(["git", "init"], cwd=temp_coding_workspace, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "TestRunner"], cwd=temp_coding_workspace, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@runner.local"], cwd=temp_coding_workspace, capture_output=True, check=True)
        subprocess.run(["git", "add", "."], cwd=temp_coding_workspace, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "Initial test commit"], cwd=temp_coding_workspace, capture_output=True, check=True)

        # 1. Create checkpoint
        res_create = git_checkpoint(action="create", repo_path=temp_coding_workspace, name="chk_phase1", message="Before modification")
        assert "checkpoint_id" in res_create
        assert res_create["message"] == "Before modification"
        cp_id = res_create["checkpoint_id"]

        # 2. List checkpoints
        res_list = git_checkpoint(action="list", repo_path=temp_coding_workspace)
        assert "checkpoints" in res_list
        assert any(cp["checkpoint_id"] == cp_id for cp in res_list["checkpoints"])

        # 3. Diff check
        res_diff = git_checkpoint(action="diff", repo_path=temp_coding_workspace, checkpoint_id=cp_id)
        assert "files_changed" in res_diff

        # 4. Delete checkpoint
        res_del = git_checkpoint(action="delete", repo_path=temp_coding_workspace, checkpoint_id=cp_id)
        assert res_del["deleted"] is True


# ==============================================================================
# TOOL 13: diagnose_error
# ==============================================================================

class TestTool13DiagnoseError:
    def test_diagnose_error_traceback_parser(self):
        tb = (
            "Traceback (most recent call last):\n"
            "  File \"src/math_utils.py\", line 15, in compute_factorial\n"
            "    raise ValueError('n must be non-negative')\n"
            "ValueError: n must be non-negative\n"
        )
        res = diagnose_error(tb)
        assert res["error_type"] == "ValueError"
        assert "n must be non-negative" in res["error_message"]
        assert "math_utils.py" in res["failing_file"]
        assert res["failing_line"] == 15
        assert "suggested_fix" in res

    def test_diagnose_error_without_fix(self):
        tb = "ZeroDivisionError: division by zero"
        res = diagnose_error(tb, suggest_fix=False)
        assert res["error_type"] == "ZeroDivisionError"
        assert "suggested_fix" not in res


# ==============================================================================
# TOOL 14: find_documentation
# ==============================================================================

class TestTool14FindDocumentation:
    def test_find_documentation_curated_library(self):
        res = find_documentation("parametrize", library="pytest")
        assert res["total_results"] >= 1
        assert res["library"] == "pytest"
        assert any("pytest.mark.parametrize" in item["symbol"] for item in res["items"])

    def test_find_documentation_ast(self):
        res = find_documentation("parse", library="ast")
        assert res["total_results"] >= 1
        assert any("ast.parse" in item["symbol"] for item in res["items"])

    def test_find_documentation_stdlib_introspection(self):
        res = find_documentation("resolve", library="pathlib")
        assert res["total_results"] >= 1


# ==============================================================================
# TOOL 15: search_coding_catalog
# ==============================================================================

class TestTool15SearchCodingCatalog:
    def test_search_coding_catalog_curated_50_repos(self):
        res = search_coding_catalog(query="", limit=100)
        assert res["status"] == "success"
        assert res["total_catalog"] == 50
        assert res["total"] == 50

    def test_search_coding_catalog_category_filter(self):
        res_a = search_coding_catalog(category="Category A")
        assert res_a["status"] == "success"
        assert res_a["total"] == 10
        for repo in res_a["repositories"]:
            assert repo["category_code"] == "A"

    def test_search_coding_catalog_keyword_search(self):
        res = search_coding_catalog(query="ripgrep")
        assert res["status"] == "success"
        assert res["total"] >= 1
        repo_names = [r["name"].lower() for r in res["repositories"]]
        assert any("ripgrep" in name for name in repo_names)

    def test_search_coding_catalog_all_active_repos(self):
        res = search_coding_catalog(query="", limit=50)
        assert res["total"] == 50
        for repo in res["repositories"]:
            assert "active" in repo["availability_status"].lower()
            assert repo["github_url"].startswith("https://github.com/")


# ==============================================================================
# COMPREHENSIVE INTEGRATION WORKFLOW
# ==============================================================================

class TestEndToEndCodingWorkflow:
    def test_full_agent_patch_and_verify_cycle(self, temp_coding_workspace: Path):
        """End-to-end integration:
        1. repo_map inspects workspace
        2. search_code locates target function
        3. read_symbol extracts AST definition
        4. propose_patch reviews diff preview
        5. apply_patch safely modifies with syntax validation
        6. verify_changes executes targeted tests
        """
        # Step 1: Map
        tree = repo_map(temp_coding_workspace, as_format="text")
        assert "math_utils.py" in tree

        # Step 2: Search
        search_res = search_code("compute_factorial", path=str(temp_coding_workspace))
        assert search_res["total_matches"] >= 1

        # Step 3: Read Symbol
        target_file = temp_coding_workspace / "src" / "math_utils.py"
        sym_res = read_symbol(str(target_file), "compute_factorial")
        assert sym_res["found"] is True

        # Step 4: Propose patch (add support for n=0 fast return)
        orig_code = target_file.read_text(encoding="utf-8")
        patched_code = orig_code.replace("if n in (0, 1):\n        return 1", "if n <= 1:\n        return 1")
        proposal = propose_patch(target_file, new_content=patched_code, workspace_root=temp_coding_workspace)
        assert proposal.diff != ""

        # Step 5: Apply patch safely
        apply_res = apply_patch(target_file, new_content=patched_code, workspace_root=temp_coding_workspace, confirm=True)
        assert apply_res.success is True
        assert apply_res.syntax_check_passed is True

        # Step 6: Verify changes
        verif = verify_changes(
            changed_files=[target_file],
            test_targets=["tests/test_math.py"],
            cwd=temp_coding_workspace,
        )
        assert verif.passed is True
        assert verif.compile_success is True
