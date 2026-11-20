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


def analyze_language(request, *, fail_on='error'):
    """Explicit full adapter invocation; serial model ownership and no writes.

    The durable dispatcher retains its existing availability contract until
    the separately planned Work integration. This callable returns the final
    language report and separate policy outcome for that integration.
    """
    from .language_policy import assess_language
    from .language_scores import decide_request
    from ._values import require
    from ..storage.language_registry import bundled_language_registry
    require(type(fail_on) is str and fail_on in ('warning', 'error'),
            'analyzer_fail_threshold', exit_code=2)
    return assess_language(request, decide_request(request),
        registry=bundled_language_registry(), fail_on=fail_on)


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
