from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if Path(__file__).with_name("ready.flag").is_file():
        return 0
    print("ready.flag is missing", file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
