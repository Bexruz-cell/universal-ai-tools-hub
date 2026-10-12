import re
import json

md_path = "catalog/top_50_repositories.md"
with open(md_path, "r", encoding="utf-8") as f:
    text = f.read()

# Parse markdown table lines: | # | **Name** | [repo](url) | Description | UseCase |
pattern = r'\|\s*(\d+)\s*\|\s*\*\*([^*]+)\*\*\s*\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|\s*([^|]+)\|\s*([^|]+)\|'
matches = re.findall(pattern, text)

repos = []
for m in matches:
    num, name, repo_slug, url, desc, use_case = m
    repos.append({
        "id": int(num),
        "name": name.strip(),
        "repo_slug": repo_slug.strip(),
        "github_url": url.strip(),
        "description": desc.strip(),
        "chatgpt_use_case": use_case.strip()
    })

print(f"Extracted {len(repos)} repositories.")
with open("catalog/catalog.json", "w", encoding="utf-8") as f:
    json.dump(repos, f, ensure_ascii=False, indent=2)

print("Saved catalog/catalog.json")
