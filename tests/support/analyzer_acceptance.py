"""Real isolated adapter probes; fault injection belongs only to the test host.

These synthetic integration inputs are not a reviewed language corpus. The
trusted test bootstrap composes the existing complete adapter and transport;
it does not claim the separately planned durable Work dispatcher is integrated.
"""
from hashlib import sha256
from pathlib import Path
import sys


from specroad.analyzers.file_adapter import default_inputs
from specroad.analyzers.subjects import request_from_project
from specroad.analyzers.worker_transport import execute
from support.domain import domain_value
from support.read_only import make_project
from support.relations import aid
from . import analyzer_runtimes
from ._analyzer_worker_fixture import WORKER

runtime_factory = analyzer_runtimes.runtime_factory


def native_request(root, cases):
    root.mkdir()
    values = [domain_value('requirement', id=aid(number=i + 1),
                           statement=text, language=language)
              for i, (language, text) in enumerate(cases)]
    make_project(root, *values)
    (root / 'unselected.txt').write_text('PRIVATE: not selected as an analyzer subject')
    return request_from_project(root, **default_inputs({}), analysis_id='acceptance:original')


def invoke_case(monkeypatch, runtime, request, mode='positive'):
    """Use real pipes/process cleanup and the production response validator."""
    from specroad.analyzers import _worker_process
    site, interpreter, _ = runtime
    assert sha256(Path(interpreter['executable']).read_bytes()).hexdigest() == interpreter['sha256']
    run_process = _worker_process.run_process
    def observed_process(*args, **kwargs):
        completed = run_process(*args, **kwargs)
        if completed.returncode != 0 and mode != 'wire:exit':
            # Preserve the actual process result and production error contract.
            # Bound diagnostics to stderr from this synthetic test worker only.
            print('Analyzer fixture worker failed: ' +
                  completed.stderr[-8192:].decode('utf-8', errors='replace'), file=sys.stderr)
        return completed
    with monkeypatch.context() as context:
        context.setattr(sys, 'executable', interpreter['executable'])
        context.setattr(_worker_process, 'distribution_path', lambda: site)
        context.setattr(_worker_process, 'run_process', observed_process)
        context.setattr(_worker_process, 'BOOTSTRAP', 'MODE = ' + repr(mode) + '\n' + WORKER)
        return execute(request)
