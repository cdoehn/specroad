"""Actual isolated CPython/Work invocations; no test work during collection."""
import json
import os
from pathlib import Path
import subprocess
from hashlib import sha256

from .analyzer_runtimes import runtime_factory as runtime_factory

__all__ = ('runtime_factory', 'invoke')

DRIVER = r'''
import json, sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from specroad.cli.application import dispatch_result
from specroad.cli.results import thaw
from specroad.cli.commands import builtin_registry
from specroad.work.open_existing import open_existing_work
from specroad.work.analyzer import checked, resume_analyzer_work, outcome
from specroad.analyzers import _work_worker
from specroad.analyzers.requests import AnalyzerRequest
from specroad.analyzers.worker_transport import execute
from specroad.runtime.consumption import WorkConsumption, CounterSample
site, action, request_file, work, trace = sys.argv[1:]
# Instrument only the trusted test bootstrap, leaving ranking, pipes, report
# validation, native checkpoints and source identity as real production paths.
probe = r"""
from pathlib import Path
from hashlib import sha256
from specroad.analyzers import _work_engine, _model_session
trace=Path(TRACE)
def record(value):
    with trace.open('a',encoding='utf-8') as out: out.write(value+'\n')
original_score=_work_engine._scores
original_load=_model_session.load_reference_model
def scored(model,text):
    record('score:'+sha256(text.encode('utf-8')).hexdigest())
    return original_score(model,text)
def loaded():
    record('load')
    return original_load()
_work_engine._scores=scored
_model_session.load_reference_model=loaded
""".replace('TRACE',repr(trace))
fault = action.split(':',1)[1] if ':' in action else None
if fault in ('crash','malformed','wrong_unit','oom'):
    probe += "\ndef broken(self,pair):\n"
    if fault=='crash': probe += " import os;os._exit(37)\n"
    elif fault=='oom': probe += " raise MemoryError('injected host allocation failure')\n"
    elif fault=='malformed': probe += " import os;os.write(1,b'{bad\\n');os._exit(0)\n"
    else: probe += " return {'foreign':'unit'}\n"
    probe += "_work_engine.WorkEngine.subject=broken\n"
elif fault=='missing_engine':
    probe += "\nfrom specroad.analyzers._values import AnalyzerError\ndef missing():raise AnalyzerError('missing_dependency',exit_code=5)\n_model_session.load_reference_model=missing\n"
elif fault=='changed_engine':
    probe += "\noriginal_enter=_work_engine.WorkEngine.__enter__\ndef changed(self):\n original_enter(self)\n self.rows[0]['engine']['model_sha256']['value']='f'*64\n return self\n_work_engine.WorkEngine.__enter__=changed\n"
if fault=='full_scratch':
    from specroad.work.checkpoints import CheckpointStore
    import errno
    def full(*args,**kwargs):raise OSError(errno.ENOSPC,'injected full scratch')
    CheckpointStore._publish_held=full
_work_worker.BOOTSTRAP=('import sys;sys.path.insert(0,sys.argv[1]);\n'+probe+
    '\nfrom specroad.analyzers._work_worker import main;raise SystemExit(main())')
if action=='single':
    request=AnalyzerRequest(Path(request_file).read_bytes())
    package=execute(request)
    print(json.dumps({'package':package.data}))
elif action=='start':
    samples=iter((0,))
    def sample():
        value=next(samples,2000000);return CounterSample(value,value,1)
    result=dispatch_result(['analyzer','run','--request',request_file,'--work-dir',work,
        '--step-wall-ms','1','--fail-on','warning'],consumption=WorkConsumption(sampler=sample))
    assert result.exit_code==8,result.as_dict()
    print(json.dumps({'code':result.exit_code,'identity':result.details['analysis_id']}))
elif action=='one':
    store=open_existing_work(Path(work),registry=builtin_registry())
    current=resume_analyzer_work(store,max_units=1)
    control,request,done=checked(current)
    value={'state':current.as_dict()['state'],'generation':current.as_dict()['checkpoint_generation'],
        'remaining':[r['key'] for r in current.entries('remaining')],
        'completed':current.entries('completed'),'done':done,'fail_on':control['fail_on'],
        'request':None if request is None else request.data}
    if value['state']=='completed':value['package'],value['code']=outcome(current)
    print(json.dumps(value))
else:
    # This action tests one model per invocation, not host speed. Keep its
    # time window open through the existing typed observer; all real engine,
    # transport, validation and durable Work paths still execute unchanged.
    consumption = (WorkConsumption(sampler=lambda: CounterSample(
        0, 0, 1, 'test_fixed_cpu', 'test_fixed_wall', 'test_fixed_rss'))
        if action == 'finish' else None)
    arguments = ['work','resume',work]
    if action == 'finish':
        # An injected observer is used only with explicit metrics or budgets.
        arguments.append('--metrics')
    result=dispatch_result(arguments, consumption=consumption)
    print(json.dumps(dict(result.as_dict(), exit_code=result.exit_code, complete=result.complete,
        continuation=None if result.continuation is None else True)))
'''


def invoke(runtime, action, request, work, trace, cwd):
    site, interpreter, _ = runtime
    assert sha256(Path(interpreter['executable']).read_bytes()).hexdigest() == interpreter['sha256']
    completed = subprocess.run([interpreter['executable'], '-I', '-S', '-B', '-c', DRIVER,
        str(site), action, str(request), str(work), str(trace)], cwd=cwd,
        env={**os.environ, 'OPENBLAS_NUM_THREADS':'1', 'OMP_NUM_THREADS':'1'},
        capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)
