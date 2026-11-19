"""Build a separate language add-on; supply original wheels, never download them."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from language_packaging.build import build_language


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--wheelhouse', type=Path, required=True)
    parser.add_argument('--python', required=True, choices=('3.10','3.11','3.12','3.13','3.14'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        build_language(Path(__file__).resolve().parents[1] / 'src', args.wheelhouse,
                       args.python, args.output)
    except (OSError, ValueError) as error:
        parser.exit(2, 'Language package unavailable: ' + str(error) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
