from __future__ import annotations

import sys


def main() -> int:
    args = sys.argv[1:]
    if args == ["--has-diff"]:
        return 1
    if args == ["--error"]:
        print("predicate execution error", file=sys.stderr)
        return 2
    print("usage: predicate.py [--has-diff|--error]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
