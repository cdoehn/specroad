"""Read-only CI binding and evidence transport, never terminal layout."""
from copy import deepcopy
from io import BytesIO, StringIO
import json
from types import SimpleNamespace
import zipfile
import pytest
from watch_bundle_ci import (Request, CIObservationError, GhClient, exact_run, find_run,
    verdict, observe_ci, records, pack_evidence, emit_evidence, recover_evidence)

SHA = 'a' * 40
REPO = 'cdoehn/specroad'


def run_value(**changes):
    value = {'id': 51, 'run_attempt': 1, 'head_sha': SHA, 'head_branch': 'dev', 'event': 'push',
             'path': '.github/workflows/behavior.yml', 'repository': {'full_name': REPO},
             'status': 'completed', 'conclusion': 'success'}
    value.update(changes)
    return value


def jobs_value(mode='parallel'):
    step = ('Full parallel regression' if mode == 'parallel'
            else 'Full parallel and serial regression with evidence comparison')
    return [{'id': i, 'run_id': 51, 'run_attempt': 1, 'head_sha': SHA, 'name': f'CPython 3.{v} / {mode}',
             'status': 'completed', 'conclusion': 'success',
             'steps': [{'name': step, 'status': 'completed', 'conclusion': 'success'}]}
            for i, v in enumerate(range(10, 15), 1)]


def zip_bytes(files=None):
    out = BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for k, v in (files or {'job.txt': b'tests completed'}).items():
            z.writestr(k, v)
    return out.getvalue()


class Client:
    def __init__(self, run=None, jobs=None, waits=0):
        self.run = run_value() if run is None else run
        self.jobs = jobs_value() if jobs is None else jobs
        self.calls = []
        self.waits = waits
        self.logs = zip_bytes()

    def document(self, path):
        self.calls.append(path)
        if 'workflows/' in path:
            if self.waits:
                self.waits -= 1
                return {'total_count': 0, 'workflow_runs': []}
            return {'total_count': 1, 'workflow_runs': [deepcopy(self.run)]}
        if '/jobs?' in path:
            return {'total_count': len(self.jobs), 'jobs': deepcopy(self.jobs)}
        if '/artifacts?' in path:
            return {'total_count': 0, 'artifacts': []}
        return deepcopy(self.run)

    def get(self, path):
        self.calls.append(path)
        return self.logs


def test_exact_finished_matrix_pass_and_logs_are_bound():
    client = Client(); progress = []
    summary, files = observe_ci(Request(SHA, 19), client=client, progress=progress.append, sleeper=lambda _: None)
    assert summary['ci_status'] == 'success' and summary['local_apply'] == 'success'
    assert summary['run_id'] == 51 and summary['run_attempt'] == 1
    assert summary['logs_captured'] is True and files['logs.zip'] == client.logs
    assert json.loads(files['jobs.json']) == client.jobs
    assert json.loads(files['run.json']) == client.run
    assert progress and any('/attempts/1/logs' in p for p in client.calls)


def test_twentieth_bundle_requires_dual_full_step():
    client = Client(jobs=jobs_value('both'))
    summary, _ = observe_ci(Request(SHA, 20), client=client, sleeper=lambda _: None)
    assert summary['ci_status'] == 'success' and summary['expected_mode'] == 'both'
    assert verdict(run_value(), jobs_value(), Request(SHA, 20)) == 'incomplete'


@pytest.mark.parametrize('bundle', [19, 21, 22, 23, 24, 26, 29, 31])
def test_normal_bundles_parallel(bundle):
    assert Request(SHA, bundle).mode == 'parallel'


@pytest.mark.parametrize('bundle', [20, 25, 30, 35, 1000])
def test_fifth_bundles_both(bundle):
    assert Request(SHA, bundle).mode == 'both'


@pytest.mark.parametrize('changes', [dict(head_sha='b'*40), dict(head_branch='main'), dict(event='workflow_dispatch'),
    dict(path='.github/workflows/other.yml'), dict(repository={'full_name':'other/repo'}),
    dict(id=0), dict(id=True), dict(run_attempt=0), dict(status='invented')])
def test_wrong_run_never_selected(changes):
    with pytest.raises(CIObservationError): exact_run(run_value(**changes), Request(SHA, 19))


def test_multiple_eligible_runs_are_not_arbitrarily_selected():
    class Multiple(Client):
        def document(self, path):
            return {'total_count': 2, 'workflow_runs': [run_value(), run_value(id=52)]}
    with pytest.raises(CIObservationError): find_run(Multiple(), Request(SHA, 19))


def test_delayed_run_is_polled_for_the_exact_sha():
    client = Client(waits=2); sleeps = []
    summary, _ = observe_ci(Request(SHA, 19), client=client, sleeper=sleeps.append)
    assert summary['ci_status'] == 'success' and len(sleeps) == 2
    assert all(SHA in p and 'event=push' in p for p in client.calls if 'workflows' in p)


def test_missing_run_is_not_success():
    summary, files = observe_ci(Request(SHA, 19), client=Client(waits=5), sleeper=lambda _: None, discovery_polls=2)
    assert summary['ci_status'] == 'unavailable' and summary['run_id'] is None
    assert summary['errors'][-1]['reason'] == 'matching_run_not_visible'
    assert 'summary.json' in files


@pytest.mark.parametrize('conclusion,status', [('failure','failed'), ('timed_out','failed'), ('cancelled','cancelled'),
                                              ('skipped','incomplete'), ('neutral','incomplete'), (None,'incomplete')])
def test_failed_cancelled_or_skipped_ci_not_green(conclusion, status):
    summary, files = observe_ci(Request(SHA, 19), client=Client(run=run_value(conclusion=conclusion)), sleeper=lambda _: None)
    assert summary['ci_status'] == status
    assert summary['local_apply'] == 'success' and 'logs.zip' in files


def test_missing_matrix_job_does_not_count_as_full_suite():
    assert verdict(run_value(), jobs_value()[:-1], Request(SHA, 19)) == 'incomplete'


def test_skipped_test_step_not_green_despite_job_success():
    jobs = jobs_value(); jobs[0]['steps'][0]['conclusion'] = 'skipped'
    assert verdict(run_value(), jobs, Request(SHA, 19)) == 'incomplete'


def test_transport_uses_only_get_fixed_host_no_shell_or_auth_output():
    calls = []
    def runner(command, **kw):
        calls.append((command, kw)); return SimpleNamespace(returncode=0, stdout=b'{}', stderr=b'')
    assert GhClient(runner).document('repos/'+REPO+'/actions/runs/51') == {}
    cmd, kw = calls[0]
    assert cmd[:7] == ['gh','api','--hostname','github.com','--method','GET','repos/'+REPO+'/actions/runs/51']
    assert not kw.get('shell') and kw['stdin'] is not None and 'GH_DEBUG' not in kw['env']
    with pytest.raises(CIObservationError): GhClient(runner).get('https://other.example/secret')


def test_auth_failure_does_not_copy_credential_diagnostics():
    c = GhClient(lambda *a, **k: SimpleNamespace(returncode=4, stdout=b'', stderr=b'secret-token'))
    with pytest.raises(CIObservationError) as err: c.document('repos/'+REPO+'/actions/runs/51')
    assert 'secret-token' not in str(err.value)


def test_ci_evidence_survives_real_result_log_transport_without_dirty_files(tmp_path):
    summary, files = observe_ci(Request(SHA, 19), client=Client(), sleeper=lambda _: None)
    raw = pack_evidence(files); output = StringIO()
    output.write('local tests passed\n'); emit_evidence(raw, output); output.write('LOCAL APPLY SUCCESS\n')
    result = tmp_path/'result.zip'
    with zipfile.ZipFile(result,'w') as z:
        z.writestr('logs/execution.log', output.getvalue())
    with zipfile.ZipFile(result) as z:
        restored = recover_evidence(z.read('logs/execution.log').decode())
    assert restored == raw
    with zipfile.ZipFile(BytesIO(restored)) as z:
        assert json.loads(z.read('summary.json'))['commit_sha'] == SHA
        assert z.read('logs.zip') == files['logs.zip']


def test_truncated_or_reordered_evidence_rejected():
    stream = StringIO(); emit_evidence(pack_evidence({'data.json': b'a'*10000}), stream)
    lines = stream.getvalue().splitlines()
    with pytest.raises(CIObservationError): recover_evidence('\n'.join(lines[:-1]))
    broken = list(lines); broken[1] = broken[1].replace('"index": 0','"index": 1')
    with pytest.raises(CIObservationError): recover_evidence('\n'.join(broken))


def test_running_job_progress_is_observed_until_completed():
    class Active(Client):
        def __init__(self): super().__init__(); self.n = 0
        def document(self, path):
            if path.endswith('/runs/51'):
                self.n += 1
                return run_value(status='in_progress',conclusion=None) if self.n == 1 else run_value()
            return super().document(path)
    progress=[]; client=Active()
    report,_=observe_ci(Request(SHA,19),client=client,progress=progress.append,sleeper=lambda _: None)
    assert client.n >= 2 and report['ci_status']=='success'
    assert any(p.get('status')=='in_progress' for p in progress)
