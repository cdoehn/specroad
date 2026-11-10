"""Explicit development-only test profiling; never part of the Core CLI."""
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

if __name__ == '__main__':
    from dev.profiling.cli import main
    raise SystemExit(main(ROOT))
