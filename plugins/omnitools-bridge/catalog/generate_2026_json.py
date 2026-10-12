import re
import json

md_path = "catalog/top_50_repositories_2026.md"
with open(md_path, "r", encoding="utf-8") as f:
    text = f.read()

# Pattern: 1. [Name](url) — desc. *Польза:* use_case.
pattern = r'(\d+)\.\s*\[([^\]]+)\]\(([^)]+)\)\s*—\s*([^*]+)\.\s*\*Польза:\*\s*([^.\n]+)'
matches = re.findall(pattern, text)

repos = []
for m in matches:
    num, name, url, desc, use_case = m
    repos.append({
        "id": int(num),
        "name": name.strip(),
        "github_url": url.strip(),
        "description": desc.strip(),
        "use_case": use_case.strip()
    })

print(f"Extracted {len(repos)} repositories from 2026 catalog.")
with open("catalog/catalog_2026.json", "w", encoding="utf-8") as f:
    json.dump(repos, f, ensure_ascii=False, indent=2)

print("Saved catalog/catalog_2026.json")
