from __future__ import annotations

import sys


def main() -> int:
    args = sys.argv[1:]
    if args == ["--help"]:
        print("usage: mini_cli.py [--help|status]")
        return 0
    if args == ["status"]:
        print("status: ready")
        return 0
    print(f"unknown option or command: {' '.join(args)}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
