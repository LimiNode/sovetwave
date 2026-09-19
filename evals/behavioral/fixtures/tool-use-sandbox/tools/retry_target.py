from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: retry_target.py PATH", file=sys.stderr)
        return 2
    target = Path(sys.argv[1])
    if not target.is_file():
        print(f"path not found: {target}", file=sys.stderr)
        return 2
    print(f"processed: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
