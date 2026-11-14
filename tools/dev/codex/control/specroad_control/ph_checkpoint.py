"""Explicit native capture seam; never Apply, commit, checkout or reset."""
import json
from pathlib import Path
import sys


def main(argv=None):
    from patchharbor import api
    from patchharbor.errors import PatchHarborError, FailureReason
    try:
        repository, repo_id, exchange = sys.argv[1:] if argv is None else argv
        repository, exchange = Path(repository), Path(exchange)
        context = api.context(repository)
        if str(context.repo_id) != repo_id or context.repository_path.value.resolve() != repository.resolve():
            raise ValueError('wrong repository')
        result = api.bundle(repository, output_directory=exchange)
        if not result.report.primary_result.success or str(result.context.repo_id) != repo_id:
            raise ValueError('capture failed')
        print(json.dumps({'ok': True, 'path': str(result.path)}))
        return 0
    except PatchHarborError as exc:
        code = 'repository_busy' if exc.reason is FailureReason.REPOSITORY_BUSY else 'checkpoint_failed'
    except (OSError, ValueError, TypeError):
        code = 'checkpoint_failed'
    print(json.dumps({'ok': False, 'error': code}))
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
