"""Distribution-owned stdin/JSON worker. No project-controlled executable paths.

Model ownership is implemented here; ranking and language decisions follow in
the separate adapter steps. Model loading alone never confirms a language.
"""
import sys
from .requests import AnalyzerRequest
from ._execution import unavailable_package
from ._values import AnalyzerError
from .registry import builtin_descriptor
from ._model_session import ModelSession


def run_request(request):
    """One serial invocation; external descriptors cannot acquire a model."""
    known = builtin_descriptor().data
    with ModelSession() as session:
        for entry in request.data['analyzers']:
            if entry['descriptor'] == known:
                try:
                    session.model()
                except AnalyzerError as error:
                    sys.stderr.write(error.reason + '\n')
        # 19.n supplies the real ranking adapter. Preserve full open coverage
        # for every selected analyzer until that separate step is implemented.
        return unavailable_package(request)


def main():
    try:
        request = AnalyzerRequest(sys.stdin.buffer.read())
        package = run_request(request)
        sys.stdout.buffer.write(package.canonical_bytes + b'\n')
        sys.stdout.buffer.flush()
    except (AnalyzerError, OSError, ValueError):
        sys.stderr.write('Invalid analyzer worker request or output.\n')
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
