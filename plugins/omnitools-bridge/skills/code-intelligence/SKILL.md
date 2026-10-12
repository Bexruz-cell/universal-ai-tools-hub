---
name: code-intelligence
description: >-
  Inspect codebase symbols, search AST patterns, generate repository structure maps,
  compute dependency graphs, and lookup official language/library documentation.
---

# Code Intelligence Skill

The `code-intelligence` skill provides structural and semantic understanding of complex codebases.

## Included Modules
1. **Symbol Extraction (`src.coding_tools.symbols`)**: Extracts classes, functions, async defs, decorators, signatures, and docstrings without executing code.
2. **Structural Search (`src.coding_tools.search`)**: Finds AST nodes and references across modules.
3. **Repository Mapper (`src.coding_tools.repo_map`)**: Visualizes file trees and symbol hierarchies for high-density LLM prompting.
4. **Dependency Graph (`src.coding_tools.deps`)**: Discovers inward and outward imports, module coupling, and affected files.
5. **Documentation Engine (`src.coding_tools.docs`)**: Retrieves standard library references and signatures.
