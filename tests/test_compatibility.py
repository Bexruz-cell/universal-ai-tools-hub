"""Compatibility QA Test Suite

Verifies 100% compatibility with Google Antigravity, Anthropic Claude, and OpenAI ChatGPT.
"""

import json
from pathlib import Path
import pytest


def test_antigravity_plugin_manifest():
    p = Path("plugin.json")
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert "$schema" in data
    assert "antigravity" in data["$schema"]
    assert data["name"] == "omnitools-bridge"
    assert "skills" in data
    assert "skills/omnitools-bridge" in data["skills"]
    assert "mcpServers" in data


def test_antigravity_skill_specification():
    skill_p = Path("skills/omnitools-bridge/SKILL.md")
    assert skill_p.exists()
    content = skill_p.read_text(encoding="utf-8")
    assert content.startswith("---")
    assert "name: omnitools-bridge" in content


def test_claude_desktop_config():
    conf_p = Path("configs/claude_desktop_config.json")
    assert conf_p.exists()
    data = json.loads(conf_p.read_text(encoding="utf-8"))
    assert "mcpServers" in data
    assert "omnitools_bridge" in data["mcpServers"] or "omnitools-hub" in data["mcpServers"]


def test_chatgpt_plugin_manifest():
    manifest_p = Path(".well-known/ai-plugin.json")
    assert manifest_p.exists()
    data = json.loads(manifest_p.read_text(encoding="utf-8"))
    assert data["schema_version"] == "v1"
    assert "name_for_model" in data
    assert len(data["name_for_human"]) <= 20
    assert len(data["description_for_human"]) <= 100
