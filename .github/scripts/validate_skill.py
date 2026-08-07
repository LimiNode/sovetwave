#!/usr/bin/env python3
"""Minimal dependency-free validation for the distributable skill."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def main() -> int:
    skill_dir = Path(sys.argv[1]) if len(sys.argv) == 2 else None
    if skill_dir is None or not (skill_dir / "SKILL.md").is_file():
        print("Expected a skill directory containing SKILL.md", file=sys.stderr)
        return 1
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not match or not re.search(r"^name:\s*[^\s]+", match.group(1), flags=re.MULTILINE) or not re.search(r"^description:\s*\S+", match.group(1), flags=re.MULTILINE):
        print("SKILL.md must begin with name and description frontmatter", file=sys.stderr)
        return 1
    print("Skill metadata is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
