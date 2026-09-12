#!/usr/bin/env python3
"""Minimal dependency-free validation for the distributable skill."""

from __future__ import annotations

import re
import json
import sys
from pathlib import Path


def main() -> int:
    release_check = "--release-metadata" in sys.argv[1:]
    arguments = [argument for argument in sys.argv[1:] if argument != "--release-metadata"]
    skill_dir = Path(arguments[0]) if len(arguments) == 1 else None
    if skill_dir is None or not (skill_dir / "SKILL.md").is_file():
        print("Expected a skill directory containing SKILL.md", file=sys.stderr)
        return 1
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not match or not re.search(r"^name:\s*[^\s]+", match.group(1), flags=re.MULTILINE) or not re.search(r"^description:\s*\S+", match.group(1), flags=re.MULTILINE):
        print("SKILL.md must begin with name and description frontmatter", file=sys.stderr)
        return 1
    errors = 0
    for relative in re.findall(r"\]\((references/[^)#]+)\)", text):
        target = skill_dir / relative
        if not target.is_file():
            print(f"Missing referenced skill resource: {relative}", file=sys.stderr)
            errors += 1

    # Release metadata is checked only by an explicitly requested release
    # validation; intermediate stacked PRs may legitimately precede the bump.
    repository = skill_dir.parents[1]
    plugin = repository / ".claude-plugin" / "plugin.json"
    changelog = repository / "CHANGELOG.md"
    if release_check and plugin.is_file() and changelog.is_file():
        try:
            plugin_version = json.loads(plugin.read_text(encoding="utf-8")).get("version")
        except (OSError, json.JSONDecodeError):
            plugin_version = None
        heading = re.search(r"^## v(\d+\.\d+\.\d+)\b", changelog.read_text(encoding="utf-8"), re.MULTILINE)
        if not isinstance(plugin_version, str) or heading is None or plugin_version != heading.group(1):
            print("Plugin version must match the newest CHANGELOG.md release heading", file=sys.stderr)
            errors += 1
    if errors:
        return 1
    print("Skill metadata is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
