"""Compatibility entry point for ``python -m evals.plan``."""

from evals.cli.plan import main

if __name__ == "__main__":
    raise SystemExit(main())
