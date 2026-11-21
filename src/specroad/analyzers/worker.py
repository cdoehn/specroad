"""Distribution-owned stdin/JSON worker. No project-controlled executable paths.

The explicit invocation owns a real serial model and complete observations.
Passive commands never enter this module's execution functions.
"""
import sys
from .requests import AnalyzerRequest
from ._values import AnalyzerError


def analyze_language(request, *, fail_on='error'):
    """Explicit full adapter invocation; serial model ownership and no writes.

    This callable and the durable dispatcher share the same subject policy.
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
    """One complete real invocation; external descriptors remain explicitly open."""
    from ._work_engine import WorkEngine
    from ._work_values import package_from_units
    values = {}
    with WorkEngine(request) as engine:
        for entry in request.data['analyzers']:
            for subject in request.data['subjects']:
                pair = dict(analyzer_id=entry['descriptor']['analyzer_id'],
                    descriptor_sha256=entry['descriptor_sha256'], subject_key=subject['subject_key'])
                values['subject:' + pair['descriptor_sha256'] + ':' + pair['subject_key']] = engine.subject(pair)
        return package_from_units(request, engine.rows, values)


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
