from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns process exit code."""
    _ = argv if argv is not None else sys.argv[1:]
    return 0
