#!/usr/bin/env python3
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = ROOT / ".agents"
SUBAGENTS_DIR = AGENTS_DIR / "subagents"

EXPECTED_SUBAGENTS = {
    "kta-mrp",
    "kta-calisma-karti",
    "kta-asset-maintenance",
    "kta-stock",
    "kta-quality",
    "kta-sales",
    "erpnextkta-core",
    "frontend-public",
    "overrides-hooks",
    "docs-i18n",
}

FORBIDDEN_PATTERNS = [
    re.compile(r"yarn\s+build"),
    re.compile(r"frappe\.db\.commit\(\)"),
]


def parse_frontmatter(content):
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None
    raw = match.group(1)
    meta = {}
    current_key = None
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line and not line.startswith("-"):
            key, val = line.split(":", 1)
            current_key = key.strip()
            val = val.strip()
            meta[current_key] = val if val else []
        elif line.startswith("-") and current_key:
            item = line.lstrip("-").strip()
            if isinstance(meta[current_key], list):
                meta[current_key].append(item)
    return meta


def main():
    errors = []
    if not SUBAGENTS_DIR.exists():
        print(f"FAIL: {SUBAGENTS_DIR} does not exist")
        sys.exit(1)

    found_agents = set()
    all_owned_paths = {}

    for file_path in SUBAGENTS_DIR.glob("*.md"):
        agent_id = file_path.stem
        found_agents.add(agent_id)
        content = file_path.read_text(encoding="utf-8")

        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(content):
                errors.append(
                    f"Forbidden pattern '{pattern.pattern}' found in {file_path.name}"
                )

        meta = parse_frontmatter(content)
        if not meta:
            errors.append(f"Missing or invalid YAML frontmatter in {file_path.name}")
            continue

        if meta.get("name") != agent_id:
            errors.append(
                f"Name mismatch in {file_path.name}: expected {agent_id}, got {meta.get('name')}"
            )
        if not meta.get("description"):
            errors.append(f"Missing description in {file_path.name}")

        owned = meta.get("owned_paths", [])
        if not owned:
            errors.append(f"Missing owned_paths in {file_path.name}")
        for path in owned:
            if path in all_owned_paths:
                errors.append(
                    f"Path overlap: {path} owned by both {all_owned_paths[path]} and {agent_id}"
                )
            all_owned_paths[path] = agent_id

    missing = EXPECTED_SUBAGENTS - found_agents
    if missing:
        errors.append(f"Missing expected subagent files: {missing}")

    if errors:
        print("VERIFICATION FAILED:")
        for err in errors:
            print(f" - {err}")
        sys.exit(1)

    print(f"SUCCESS: All {len(found_agents)} subagents verified with zero overlaps.")


if __name__ == "__main__":
    main()
