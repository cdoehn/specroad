"""Module entry point; no independent command implementation."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
