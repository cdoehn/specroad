"""Recover the archive carried inside a PatchHarbor Result's execution log."""
import argparse
from pathlib import Path
import zipfile
import sys
TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from watch_bundle_ci import recover_evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    with zipfile.ZipFile(args.result) as archive:
        raw = recover_evidence(archive.read('logs/execution.log').decode('utf-8'))
    with args.output.open('xb') as out:
        out.write(raw)


if __name__ == '__main__':
    main()
