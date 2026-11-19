"""Narrow trusted process boundary, separate from analyzer route selection."""
import os
from pathlib import Path
import subprocess
import sys
import zipimport

from ._values import AnalyzerError, require
from .packages import ReportPackage
from .requests import AnalyzerRequest

BOOTSTRAP = ('import sys; sys.path.insert(0, sys.argv[1]); '
             'from specroad.analyzers.worker import main; raise SystemExit(main())')


def distribution_path():
    import specroad
    loader = specroad.__loader__
    if isinstance(loader, zipimport.zipimporter):
        return Path(loader.archive).resolve(strict=True)
    return Path(specroad.__file__).resolve(strict=True).parent.parent


def invoke_worker(request):
    require(type(request) is AnalyzerRequest, 'analyzer_request_required', exit_code=2)
    interpreter = Path(sys.executable).absolute()
    require(interpreter.is_file(), 'analyzer_worker_interpreter_unavailable', exit_code=5)
    distribution = distribution_path()
    command = [str(interpreter), '-I', '-S', '-B', '-c', BOOTSTRAP, str(distribution)]
    try:
        completed = subprocess.run(command, input=request.canonical_bytes,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=distribution if distribution.is_dir() else distribution.parent,
            env={'PATH':os.defpath, 'LANG':'C.UTF-8'}, shell=False, check=False)
        require(completed.returncode == 0, 'analyzer_worker_failed', exit_code=5)
        try:
            package = ReportPackage(completed.stdout, request=request)
            names = [r.data['analyzer']['descriptor']['analyzer_id'] for r in package.reports]
            require(len(names) == len(set(names)) == len(request.data['analyzers']),
                    'analyzer_worker_duplicate_analyzer')
        except AnalyzerError as error:
            raise AnalyzerError('analyzer_worker_invalid_response', exit_code=5) from error
        return package
    except OSError as error:
        raise AnalyzerError('analyzer_worker_unavailable', exit_code=5) from error
