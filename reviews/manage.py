"""Portable review CLI, usable directly from a clone with Python 3.10+."""
import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from reviews.reviewlib import ReviewError, run


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('validate', 'summary'))
    args = parser.parse_args(argv)
    try:
        result = run(Path(__file__).absolute().parent, args.command)
    except (ReviewError, OSError) as exc:
        print(json.dumps(dict(valid=False, error=str(exc)), ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
