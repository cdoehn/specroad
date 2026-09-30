"""Manual-only execution, exact dispatch binding and independent evidence contracts."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
import subprocess
from types import SimpleNamespace
import zipfile
import pytest

from ci_support.contract import Request, CIObservationError, exact_run
from ci_support.observer import observe_ci
from ci_support.evidence import inspect_report_archive
from ci_support.runners import runner_labels
from select_bundle_ci import resolve_selection
from test_bundle_ci import message
from verification_support.bundle_ci import select_ci
from test_ci_wait import SHA, Client, run_value, jobs_value, zip_bytes
from test_ci_wait_right import ArtifactClient, SOURCE, report_zip

WORKFLOW_SHA = 'b' * 40


def manual_client(*, test_sha=SHA, workflow_sha=SHA):
    client = ArtifactClient('both', run=run_value(event='workflow_dispatch', head_sha=workflow_sha))
    for job in client.jobs:
        job['head_sha'] = workflow_sha
    for index, version in enumerate(('3.10', '3.11', '3.12', '3.13', '3.14'), 101):
        with zipfile.ZipFile(BytesIO(client.archives[index])) as archive:
            files = {name: archive.read(name) for name in archive.namelist()}
        context = {'format_version': 1, 'repository': 'cdoehn/specroad', 'branch': 'dev',
                   'event': 'workflow_dispatch', 'mode': 'both', 'python': version,
                   'test_commit_sha': test_sha, 'workflow_commit_sha': workflow_sha,
                   'run_id': 51, 'run_attempt': 1}
        files['run-context.json'] = json.dumps(context).encode()
        raw = zip_bytes(files)
        client.archives[index] = raw
        client.artifacts[index-101].update(name=f'behavior-{version}-{test_sha}-attempt-1',
            digest='sha256:' + sha256(raw).hexdigest(),
            workflow_run={'id': 51, 'head_sha': workflow_sha, 'head_branch': 'dev'})
    return client


def git_runner(cmd, **kwargs):
    return SimpleNamespace(stdout=(SHA+'\n' if cmd[1]=='rev-parse' else message(41) if cmd[1]=='show' else '').encode())


@pytest.mark.parametrize('number', [40, 41, 45, 50])
def test_no_push_performs_git_runner_probe_or_tests(number):
    calls = []
    assert not select_ci('push','refs/heads/dev',SHA,message(number))['run_full']
    value = resolve_selection({'GITHUB_EVENT_NAME': 'push', 'GITHUB_REF': 'refs/heads/dev',
        'GITHUB_SHA': SHA, 'SR_CI_MODE': 'auto'}, runner=lambda *a, **k: calls.append(a),
        probe=lambda: calls.append('probe'))
    assert value['run_full'] is False and value['runner_selection'] is None
    assert calls == []


@pytest.mark.parametrize('ref', ['refs/heads/main', '', 'refs/tags/v1'])
def test_manual_dispatch_requires_explicit_dev_branch(ref):
    with pytest.raises(ValueError):
        resolve_selection({'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_REF': ref,
            'GITHUB_SHA': SHA}, runner=lambda *a, **k: pytest.fail('must not run git'))


@pytest.mark.parametrize('choice', ['auto', 'hetzner'])
def test_requested_hetzner_still_requires_fresh_available_runner(choice):
    count = []
    def probe():
        count.append(1)
        return {'format_version': 1, 'repository': 'cdoehn/specroad', 'reservation': False,
                'choice': 'github-hosted', 'runs_on': runner_labels('github-hosted'),
                'reason': 'hetzner_offline'}
    selection = resolve_selection({'GITHUB_EVENT_NAME':'workflow_dispatch',
        'GITHUB_REF':'refs/heads/dev', 'GITHUB_SHA':SHA, 'SR_CI_RUNNER':choice},
        runner=git_runner, probe=probe)
    assert count == [1] and selection['runner_choice'] == 'github-hosted'
    assert selection['mode'] == 'both' and selection['run_full'] is True


def test_explicit_hosted_selection_does_not_probe_or_require_administration_token():
    selection = resolve_selection({'GITHUB_EVENT_NAME':'workflow_dispatch',
        'GITHUB_REF':'refs/heads/dev', 'GITHUB_SHA':WORKFLOW_SHA, 'SR_COMMIT_SHA':SHA,
        'SR_CI_RUNNER':'github-hosted'}, runner=git_runner,
        probe=lambda: pytest.fail('must not query runner'))
    assert selection['commit_sha'] == SHA and selection['workflow_commit_sha'] == WORKFLOW_SHA
    assert selection['runner_selection']['reason'] == 'explicit_hosted_request'


@pytest.mark.parametrize('bad', [None, {}, {'format_version':1, 'repository':'cdoehn/specroad',
    'reservation':False, 'choice':'hetzner', 'runs_on':['self-hosted','ubuntu-24.04']}])
def test_malformed_probe_does_not_become_an_unchecked_runner_expression(bad):
    with pytest.raises(ValueError):
        resolve_selection({'GITHUB_EVENT_NAME':'workflow_dispatch',
            'GITHUB_REF':'refs/heads/dev', 'GITHUB_SHA':SHA}, runner=git_runner, probe=lambda: bad)


def test_complete_manual_dual_matrix_is_bound_to_test_and_workflow_sha_separately():
    client = manual_client(workflow_sha=WORKFLOW_SHA)
    request = Request(SHA, 41, SOURCE, workflow_commit=WORKFLOW_SHA)
    summary, files = observe_ci(request, client=client, sleeper=lambda _:None,
                               pinned_run_id=51, pinned_attempt=1)
    assert summary['ci_status'] == 'success' and summary['evidence_complete']
    assert summary['local_apply'] == 'not_observed'
    assert summary['trigger_event'] == 'workflow_dispatch'
    assert summary['commit_sha'] == SHA and summary['workflow_commit_sha'] == WORKFLOW_SHA
    assert len(summary['test_reports']) == 5
    assert all(r['mode']=='both' and r['comparison']['equivalent'] for r in summary['test_reports'])
    assert files['reports-3.10.zip'] == client.archives[101]


def test_manual_discovery_filters_dispatch_revision_and_event_not_moving_branch():
    client = manual_client(workflow_sha=WORKFLOW_SHA)
    summary, _ = observe_ci(Request(SHA, None, SOURCE, workflow_commit=WORKFLOW_SHA),
                            client=client, sleeper=lambda _:None)
    assert summary['ci_status'] == 'success'
    discovery = next(p for p in client.calls if '/workflows/' in p)
    assert 'event=workflow_dispatch' in discovery and 'head_sha='+WORKFLOW_SHA in discovery
    assert 'head_sha='+SHA not in discovery


def test_multiple_manual_runs_require_a_pin_not_the_latest_green_run():
    class Multiple(Client):
        def document(self, path):
            if '/workflows/' in path:
                return {'total_count':2,'workflow_runs':[run_value(event='workflow_dispatch'),
                    run_value(id=52,event='workflow_dispatch')]}
            return super().document(path)
    summary, _ = observe_ci(Request(SHA,41,SOURCE),client=Multiple(),sleeper=lambda _:None)
    assert summary['ci_status'] == 'unavailable' and not summary['run_binding_confirmed']


@pytest.mark.parametrize('change', [{'run_id':52}, {'run_attempt':2}, {'test_commit_sha':'c'*40},
    {'workflow_commit_sha':'d'*40}, {'event':'push'}, {'python':'3.11'}, {'mode':'parallel'},
    {'branch':'main'}, {'repository':'another/repo'}, {'run_id':True}])
def test_manual_context_cannot_be_borrowed_from_other_revision_run_attempt_or_mode(change):
    client = manual_client(workflow_sha=WORKFLOW_SHA)
    with zipfile.ZipFile(BytesIO(client.archives[101])) as archive:
        files = {name:archive.read(name) for name in archive.namelist()}
    value = json.loads(files['run-context.json']); value.update(change)
    files['run-context.json'] = json.dumps(value).encode()
    with pytest.raises(CIObservationError, match='manual_test_context_mismatch'):
        inspect_report_archive(zip_bytes(files),Request(SHA,41,SOURCE,workflow_commit=WORKFLOW_SHA),
            '3.10',run_id=51,attempt=1)


def test_manual_reports_require_context_but_explicit_historical_reports_remain_readable():
    raw = report_zip(mode='both')
    with pytest.raises(CIObservationError):
        inspect_report_archive(raw,Request(SHA,40,SOURCE),'3.10')
    result = inspect_report_archive(raw,Request(SHA,40,SOURCE,event='push',expected_mode='both'),'3.10')
    assert result['comparison']['equivalent'] is True


@pytest.mark.parametrize('options', [dict(expected_mode='parallel'), dict(event='schedule'),
    dict(workflow_commit='abc'), dict(event='push',bundle=None),
    dict(event='push',bundle=41,workflow_commit=WORKFLOW_SHA)])
def test_invalid_or_ambiguous_request_contract(options):
    with pytest.raises(CIObservationError):
        Request(SHA, **options)


def test_standalone_observer_rejects_unbound_current_checkout_before_network(tmp_path, monkeypatch):
    import watch_bundle_ci as tool
    calls=[]
    monkeypatch.setattr(tool,'observe_ci',lambda *a,**k:calls.append(a))
    monkeypatch.setattr(tool.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout=(WORKFLOW_SHA+'\n').encode()))
    with pytest.raises(SystemExit) as caught:
        tool.main(['--commit',SHA,'--output-dir',str(tmp_path/'out')])
    assert caught.value.code == 2 and calls == []


def test_standalone_observer_forwards_explicit_manual_pin_without_asserting_apply(tmp_path, monkeypatch):
    import watch_bundle_ci as tool
    calls=[]
    def observe(request,**options):
        calls.append((request,options))
        return observe_ci(request,client=manual_client(workflow_sha=WORKFLOW_SHA),sleeper=lambda _:None,
            pinned_run_id=options['pinned_run_id'],pinned_attempt=options['pinned_attempt'])
    monkeypatch.setattr(tool,'observe_ci',observe)
    assert tool.main(['--commit',SHA,'--workflow-commit',WORKFLOW_SHA,'--source-sha256',SOURCE,
        '--run-id','51','--attempt','1','--output-dir',str(tmp_path/'out')]) == 0
    saved=json.loads((tmp_path/'out'/'ci-summary.json').read_text())
    assert saved['ci_status']=='success' and saved['local_apply']=='not_observed'
    assert calls[0][0].mode=='both' and calls[0][0].event=='workflow_dispatch'
    assert calls[0][1]['pinned_run_id']==51 and calls[0][1]['pinned_attempt']==1


def test_green_dispatch_for_unproven_input_is_not_a_success_for_requested_test_sha():
    client = manual_client(test_sha='d'*40, workflow_sha=WORKFLOW_SHA)
    summary, files = observe_ci(Request(SHA,41,SOURCE,workflow_commit=WORKFLOW_SHA),
        client=client, sleeper=lambda _:None, pinned_run_id=51, pinned_attempt=1)
    assert summary['github_conclusion']=='success' and summary['ci_status']=='incomplete'
    assert not summary['test_evidence_verified'] and not summary['evidence_complete']
