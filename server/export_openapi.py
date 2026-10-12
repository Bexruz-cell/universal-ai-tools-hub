import json
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.adapters.api_adapter import app

openapi_schema = app.openapi()

# Save JSON to both server/ and root
for loc in [Path(__file__).resolve().parent / "openapi.json", Path(__file__).resolve().parent.parent / "openapi.json"]:
    with open(loc, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2, ensure_ascii=False)

# Convert to YAML
try:
    import yaml
    for loc in [Path(__file__).resolve().parent / "openapi.yaml", Path(__file__).resolve().parent.parent / "openapi.yaml"]:
        with open(loc, "w", encoding="utf-8") as f:
            yaml.dump(openapi_schema, f, sort_keys=False, allow_unicode=True)
    print("Exported openapi.json and openapi.yaml successfully.")
except ImportError:
    print("Exported openapi.json.")
