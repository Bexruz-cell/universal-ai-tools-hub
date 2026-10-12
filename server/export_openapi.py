import json
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from server.main import app

openapi_schema = app.openapi()

# Save JSON
json_path = Path(__file__).resolve().parent / "openapi.json"
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(openapi_schema, f, indent=2, ensure_ascii=False)

# Convert to YAML format if pyyaml installed, or formatted string
try:
    import yaml
    yaml_path = Path(__file__).resolve().parent / "openapi.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(openapi_schema, f, sort_keys=False, allow_unicode=True)
    print("Exported openapi.json and openapi.yaml")
except ImportError:
    # Basic fallback export
    print("Exported openapi.json (PyYAML not installed, JSON is natively supported by ChatGPT)")
