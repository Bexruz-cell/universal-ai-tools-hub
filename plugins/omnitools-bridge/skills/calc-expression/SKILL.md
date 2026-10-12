---
name: calc-expression
description: >-
  Safely evaluate complex mathematical expressions, arithmetic, percentages, algebraic formulas,
  and financial calculations with high precision and zero arbitrary code execution risk. Use this skill
  when the user requires exact numeric computations, conversions, financial modeling, or math verification
  that LLMs might miscalculate.
---

# Safe Math Calculator Skill

The `calc-expression` skill provides a sandboxed, deterministic mathematical computation engine. It replaces unreliable LLM arithmetic with exact Python AST evaluation, completely eliminating calculation hallucinations while protecting against code-injection vulnerabilities.

## Architecture & Interfaces

1. **MCP Tool**: `calc_expression(expression, precision)` via stdio bridge.
2. **REST API**: `POST /tools/calc` via `api_adapter.py`.
3. **Python SDK**: `from src.core.tools import calc_expression`.

## Sandbox Security Guarantee

The engine parses expressions into an Abstract Syntax Tree (AST) allowing only:
- Numeric literals (`int`, `float`)
- Binary & unary operators (`+`, `-`, `*`, `/`, `//`, `%`, `**`)
- Whitelisted mathematical functions: `sqrt`, `sin`, `cos`, `tan`, `log`, `log10`, `log2`, `exp`, `abs`, `round`, `floor`, `ceil`, `min`, `max`, `pow`
- Mathematical constants: `pi`, `e`, `tau`
- **Strictly Disallowed**: `eval()`, `exec()`, imports, variables, attributes, indexing, or arbitrary statement execution.

## Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `expression` | string | **Yes** | — | Mathematical formula string (e.g. `(15000 * 1.075)**3 / 12`). |
| `precision` | integer | No | `4` | Decimal places to round output (0–10). Default is `4`. |

## Usage Examples

### 1. Antigravity / Claude / Codex MCP Tool Call
```json
{
  "name": "calc_expression",
  "arguments": {
    "expression": "sqrt(144) + 10 * 2",
    "precision": 2
  }
}
```

### 2. HTTP / REST API (ChatGPT Custom Action)
```http
POST /tools/calc HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "expression": "sqrt(144) + (2500 * (1 + 0.08 / 12)**(12 * 5))",
  "precision": 2
}
```
