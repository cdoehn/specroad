"""Distribution-owned executable selection; descriptor files remain passive."""
from ._values import encoded, require
from .descriptors import AnalyzerDescriptor
from .registry import builtin_descriptor
from .requests import AnalyzerRequest
from ._worker_process import invoke_worker as invoke_worker, distribution_path as distribution_path
from ._worker_process import subprocess as subprocess

__all__ = ('invoke_worker','distribution_path','subprocess','execute')

def execute(request):
    """Only our exact registered descriptor can select this executable route."""
    require(type(request) is AnalyzerRequest, 'analyzer_request_required', exit_code=2)
    known = builtin_descriptor().canonical_bytes
    selected = any(AnalyzerDescriptor(encoded(row['descriptor'])).canonical_bytes == known
                   for row in request.data['analyzers'])
    if not selected:
        from ._execution import unavailable_package
        return unavailable_package(request)
    return invoke_worker(request)
