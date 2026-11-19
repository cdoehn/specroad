"""Distribution-owned stdin/JSON worker. No project-controlled executable paths.

The transport is executable; the real reference engine is planned in 19.n.
Until then every subject remains honestly open and the run unavailable.
"""
import sys
from .requests import AnalyzerRequest
from ._execution import unavailable_package
from ._values import AnalyzerError


def main():
    try:
        request = AnalyzerRequest(sys.stdin.buffer.read())
        package = unavailable_package(request)
        sys.stdout.buffer.write(package.canonical_bytes + b'\n')
        sys.stdout.buffer.flush()
    except (AnalyzerError, OSError, ValueError):
        sys.stderr.write('Invalid analyzer worker request or output.\n')
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
