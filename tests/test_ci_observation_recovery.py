"""Pinned read-only recovery and retained partial evidence, not terminal text."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO, StringIO
import json
from types import SimpleNamespace
import zipfile

import pytest
from watch_bundle_ci import (Request, CIObservationError, GhClient, observe_ci,
                            pack_evidence, emit_evidence, recover_evidence)
from test_ci_wait import Client, SHA, REPO, run_value, jobs_value
from test_ci_wait_right import ArtifactClient, SOURCE, report_zip


def test_pinned_attempt_ignores_a_different_latest_attempt_and_never_discovers():
    class Historical(ArtifactClient):
        def document(self, path):
            assert '/workflows/' not in path and not path.endswith('/runs/51')
            return super().document(path)
    client = Historical()
    summary, files = observe_ci(Request(SHA, 38, SOURCE), client=client,
        sleeper=lambda _: None, pinned_run_id=51, pinned_attempt=1)
    assert summary['ci_status'] == 'success' and summary['evidence_complete']
    assert summary['run_binding_confirmed'] is True and summary['pinned_attempt'] is True
    assert (summary['run_id'], summary['run_attempt']) == (51, 1)
    assert summary['source_sha256'] == SOURCE
    assert json.loads(files['run.json'])['run_attempt'] == 1
    assert any(p.endswith('/runs/51/attempts/1') for p in client.calls)


@pytest.mark.parametrize('run_id,attempt', [(None, 1), (51, None), (True, 1), (51, True),
    (0, 1), (-1, 1), (51, 0), ('51', 1), (51, '1')])
def test_invalid_or_half_pins_are_rejected_before_transport(run_id, attempt):
    client = Client()
    with pytest.raises(CIObservationError):
        observe_ci(Request(SHA, 38), client=client, sleeper=lambda _: None,
                   pinned_run_id=run_id, pinned_attempt=attempt)
    assert client.calls == []


@pytest.mark.parametrize('changes', [dict(id=52), dict(run_attempt=2), dict(head_sha='b'*40),
    dict(head_branch='main'), dict(repository={'full_name': 'wrong/repo'})])
def test_wrong_pinned_response_is_not_recovered_or_replaced(changes):
    client = Client(run=run_value(**changes))
    summary, files = observe_ci(Request(SHA, 38, SOURCE), client=client,
        sleeper=lambda _: None, pinned_run_id=51, pinned_attempt=1)
    assert summary['ci_status'] == 'unavailable' and not summary['run_binding_confirmed']
    assert not any(name.endswith('.zip') for name in files)
    assert len(client.calls) == 1


def test_missing_pinned_attempt_keeps_the_requested_binding_without_claiming_it_confirmed():
    class Missing(Client):
        def document(self, path):
            self.calls.append(path)
            raise CIObservationError('gh_api_exit_1')
    client = Missing()
    summary, files = observe_ci(Request(SHA, 38, SOURCE), client=client,
        sleeper=lambda _: None, pinned_run_id=51, pinned_attempt=1)
    assert summary['ci_status'] == 'unavailable' and not summary['run_binding_confirmed']
    assert (summary['run_id'], summary['run_attempt']) == (51, 1)
    assert len(client.calls) == 3 and all(p.endswith('/runs/51/attempts/1') for p in client.calls)
    assert set(files) == {'summary.json'}


class PollOutage(ArtifactClient):
    """One failed matrix job is known before the run endpoint stops responding."""
    def __init__(self, *, identity_change=False):
        super().__init__()
        self.polls = 0
        self.identity_change = identity_change
        self.jobs = jobs_value()
        self.jobs[0]['conclusion'] = 'failure'
        self.jobs[0]['steps'][0]['conclusion'] = 'failure'
        for job in self.jobs[1:]:
            job.update(status='queued', conclusion=None, steps=[])
        raw = report_zip(changes={'suite_passed': False})
        self.archives[101] = raw
        self.artifacts = self.artifacts[:1]
        self.artifacts[0]['digest'] = 'sha256:' + sha256(raw).hexdigest()
    def document(self, path):
        if path.endswith('/runs/51'):
            self.calls.append(path)
            self.polls += 1
            if self.polls == 1:
                return run_value(status='in_progress', conclusion=None)
            if self.identity_change:
                return run_value(run_attempt=2)
            raise CIObservationError('gh_api_exit_1')
        return super().document(path)
    def get(self, path):
        self.calls.append(path)
        if path.endswith('/attempts/1/logs'):
            raise CIObservationError('gh_api_exit_1')
        if path.endswith('/jobs/1/logs'):
            return b'failed test traceback, complete job log\n'
        return super().get(path)


def test_transport_outage_salvages_known_failed_job_and_available_failed_report():
    client = PollOutage()
    summary, files = observe_ci(Request(SHA, 38, SOURCE), client=client, sleeper=lambda _: None)
    assert summary['ci_status'] == 'unavailable' and summary['github_conclusion'] is None
    assert not summary['evidence_complete'] and not summary['test_evidence_verified']
    assert summary['observed_failures'][0]['job_id'] == 1
    assert summary['observed_failures'][0]['conclusion'] == 'failure'
    assert files['job-1-attempt-1.log'] == b'failed test traceback, complete job log\n'
    assert files['reports-3.10.zip'] == client.archives[101]
    assert not summary['logs_captured'] and summary['job_logs_captured'] == [1]
    assert json.loads(files['jobs.json'])[0]['conclusion'] == 'failure'
    assert not any('/jobs/2/logs' in p for p in client.calls)
    assert not any('/rerun' in p or '/cancel' in p for p in client.calls)
    for name, metadata in summary['files'].items():
        assert metadata == {'size': len(files[name]), 'sha256': sha256(files[name]).hexdigest()}


def test_integrity_change_does_not_trigger_transport_salvage_or_mix_attempts():
    client = PollOutage(identity_change=True)
    summary, files = observe_ci(Request(SHA, 38, SOURCE), client=client, sleeper=lambda _: None)
    assert summary['ci_status'] == 'unavailable' and not summary['evidence_complete']
    assert not any(p.endswith('/logs') or '/artifacts' in p for p in client.calls)
    assert summary['observed_failures'][0]['job_id'] == 1
    assert 'run.json' in files and 'jobs.json' in files


def test_run_snapshot_is_saved_even_when_jobs_cannot_be_loaded():
    class JobsOutage(ArtifactClient):
        def document(self, path):
            if '/jobs?' in path:
                raise CIObservationError('gh_api_exit_1')
            return super().document(path)
    summary, files = observe_ci(Request(SHA, 38, SOURCE), client=JobsOutage(), sleeper=lambda _: None)
    assert summary['ci_status'] == 'unavailable'
    assert json.loads(files['run.json'])['head_sha'] == SHA
    assert 'jobs.json' not in files and 'logs.zip' in files
    assert not summary['evidence_complete'] and not summary['test_evidence_verified']


def test_pinned_failed_attempt_remains_failed_with_full_logs():
    client = ArtifactClient(run=run_value(conclusion='failure'))
    summary, files = observe_ci(Request(SHA, 38, SOURCE), client=client,
        sleeper=lambda _: None, pinned_run_id=51, pinned_attempt=1)
    assert summary['ci_status'] == 'failed' and summary['github_conclusion'] == 'failure'
    assert files['logs.zip'] == client.logs


@pytest.mark.parametrize('http_status', [401, 403, 404, 429, 500, 503])
def test_http_status_is_retained_without_credentials_or_raw_gh_diagnostics(http_status):
    secret = b'Authorization: Bearer secret-token\n'
    client = GhClient(lambda *a, **k: SimpleNamespace(returncode=1, stdout=secret,
        stderr=secret + f'gh: request rejected (HTTP {http_status})\n'.encode()))
    with pytest.raises(CIObservationError) as caught:
        client.document('repos/' + REPO + '/actions/runs/51')
    assert caught.value.http_status == http_status and caught.value.returncode == 1
    assert 'secret-token' not in str(caught.value)


def test_error_summary_preserves_only_structured_transport_metadata():
    client = GhClient(lambda *a, **k: SimpleNamespace(returncode=1, stdout=b'',
        stderr=b'secret-token (HTTP 403)'))
    summary, files = observe_ci(Request(SHA, 38), client=client, sleeper=lambda _: None,
                               pinned_run_id=51, pinned_attempt=1)
    assert summary['errors'][0]['http_status'] == 403
    assert summary['errors'][0]['returncode'] == 1
    assert b'secret-token' not in b''.join(files.values())


def recovery_binding():
    return {'repository': REPO, 'branch': 'dev', 'workflow_path': '.github/workflows/behavior.yml',
            'commit_sha': SHA, 'bundle_number': 38, 'run_id': 51, 'run_attempt': 1, 'source_sha256': SOURCE}


def test_prior_binding_keeps_old_source_independent_of_current_source():
    from watch_bundle_ci import parse_recovery_binding
    request, run_id, attempt = parse_recovery_binding(recovery_binding())
    assert request == Request(SHA, 38, SOURCE) and (run_id, attempt) == (51, 1)


@pytest.mark.parametrize('change', [{'source_sha256': None}, {'run_id': True}, {'run_attempt': 0},
    {'repository': 'other/repo'}, {'branch': 'main'}, {'workflow_path': 'wrong.yml'},
    {'commit_sha': 'a'*7}, {'bundle_number': 0}, {'unknown': 1}])
def test_unbound_prior_context_rejected(change):
    from watch_bundle_ci import parse_recovery_binding
    value = recovery_binding(); value.update(change)
    with pytest.raises(CIObservationError):
        parse_recovery_binding(value)


def test_prior_and_current_evidence_use_one_existing_result_frame():
    from watch_bundle_ci import attach_prior_evidence
    prior, old_files = observe_ci(Request(SHA, 38, SOURCE), client=ArtifactClient(run=run_value(conclusion='failure')),
        sleeper=lambda _: None, pinned_run_id=51, pinned_attempt=1)
    current, files = observe_ci(Request(SHA, 39, SOURCE), client=ArtifactClient(), sleeper=lambda _: None)
    before = pack_evidence(old_files)
    attach_prior_evidence(current, files, prior, old_files)
    assert current['ci_status'] == 'success' and current['bundle_number'] == 39
    assert current['prior_ci']['ci_status'] == 'failed' and current['prior_ci']['bundle_number'] == 38
    assert current['prior_ci']['run_id'] == 51 and current['prior_ci']['run_attempt'] == 1
    assert files['prior-ci-evidence.zip'] == before
    stream = StringIO(); emit_evidence(pack_evidence(files), stream)
    restored = recover_evidence(stream.getvalue())
    with zipfile.ZipFile(BytesIO(restored)) as z:
        assert z.read('prior-ci-evidence.zip') == before
        combined = json.loads(z.read('summary.json'))
        assert combined['files']['prior-ci-evidence.zip']['sha256'] == sha256(before).hexdigest()
        assert combined['ci_status'] == 'success' and combined['prior_ci']['ci_status'] == 'failed'


def test_prior_capture_failure_never_changes_current_verdict():
    from watch_bundle_ci import attach_prior_evidence
    prior = {'bundle_number': 38, 'commit_sha': SHA, 'run_id': 51, 'run_attempt': 1,
             'ci_status': 'unavailable', 'evidence_complete': False}
    current, files = observe_ci(Request(SHA, 39), client=Client(), sleeper=lambda _: None)
    attach_prior_evidence(current, files, prior, {'summary.json': json.dumps(prior).encode()})
    assert current['ci_status'] == 'success' and current['prior_ci']['ci_status'] == 'unavailable'


def cli_arguments(tmp_path, *, push_failed=False):
    binding = tmp_path / 'previous.json'
    binding.write_text(json.dumps(recovery_binding()), encoding='utf-8')
    args = ['--commit', SHA, '--bundle', '39', '--output-dir', str(tmp_path / 'out'),
            '--recover-prior', str(binding)]
    return args + (['--push-failed'] if push_failed else [])


def test_cli_observes_current_first_and_carries_both_exact_requests(tmp_path, monkeypatch, capsys):
    import watch_bundle_ci as tool
    calls = []
    def observe(request, **options):
        calls.append((request, options))
        return observe_ci(request, client=ArtifactClient(), sleeper=lambda _: None,
                          **{key: value for key, value in options.items() if key.startswith('pinned_')})
    monkeypatch.setattr(tool, 'observe_ci', observe)
    assert tool.main(cli_arguments(tmp_path)) == 0
    assert [request.bundle for request, _ in calls] == [39, 38]
    assert calls[0][1].get('pinned_run_id') is None
    assert calls[1][0].source_sha256 == SOURCE
    assert (calls[1][1]['pinned_run_id'], calls[1][1]['pinned_attempt']) == (51, 1)
    raw = recover_evidence(capsys.readouterr().out)
    assert raw == (tmp_path / 'out' / 'ci-evidence.zip').read_bytes()
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        summary = json.loads(archive.read('summary.json'))
        assert summary['bundle_number'] == 39 and summary['prior_ci']['bundle_number'] == 38
        with zipfile.ZipFile(BytesIO(archive.read('prior-ci-evidence.zip'))) as old:
            assert json.loads(old.read('summary.json'))['source_sha256'] == SOURCE


def test_cli_push_failure_skips_current_discovery_but_preserves_old_attempt(tmp_path, monkeypatch, capsys):
    import watch_bundle_ci as tool
    calls = []
    def observe(request, **options):
        calls.append((request, options))
        return observe_ci(request, client=ArtifactClient(), sleeper=lambda _: None,
                          pinned_run_id=options['pinned_run_id'], pinned_attempt=options['pinned_attempt'])
    monkeypatch.setattr(tool, 'observe_ci', observe)
    assert tool.main(cli_arguments(tmp_path, push_failed=True)) == 0
    assert len(calls) == 1 and calls[0][0].bundle == 38
    with zipfile.ZipFile(BytesIO(recover_evidence(capsys.readouterr().out))) as archive:
        summary = json.loads(archive.read('summary.json'))
        assert summary['ci_status'] == 'not_published'
        assert summary['prior_ci']['run_attempt'] == 1


def test_cli_rejects_invalid_prior_binding_before_any_observation(tmp_path, monkeypatch):
    import watch_bundle_ci as tool
    calls = []
    monkeypatch.setattr(tool, 'observe_ci', lambda *a, **k: calls.append(a))
    args = cli_arguments(tmp_path)
    (tmp_path / 'previous.json').write_text('{"repository":"other/repo"}', encoding='utf-8')
    with pytest.raises(SystemExit) as error:
        tool.main(args)
    assert error.value.code == 2 and calls == []


def test_cli_prior_packing_limit_preserves_outcome_without_claiming_missing_files(tmp_path, monkeypatch, capsys):
    import watch_bundle_ci as tool
    def observe(request, **options):
        return observe_ci(request, client=ArtifactClient(), sleeper=lambda _: None)
    original = tool.pack_evidence
    def fail_prior(files):
        if json.loads(files['summary.json'])['bundle_number'] == 38:
            raise CIObservationError('total_evidence_limit')
        return original(files)
    monkeypatch.setattr(tool, 'observe_ci', observe)
    monkeypatch.setattr(tool, 'pack_evidence', fail_prior)
    assert tool.main(cli_arguments(tmp_path)) == 0
    with zipfile.ZipFile(BytesIO(recover_evidence(capsys.readouterr().out))) as archive:
        assert archive.namelist() == ['summary.json']
        summary = json.loads(archive.read('summary.json'))
        assert summary['ci_status'] == 'success'
        assert not summary['evidence_complete'] and not summary['test_evidence_verified']
        assert summary['files'] == {} and not summary['logs_captured']
        assert summary['prior_ci']['evidence_file'] is None
        assert summary['transport_dropped_files']


def test_cli_interrupt_does_not_start_another_observation(tmp_path, monkeypatch, capsys):
    import watch_bundle_ci as tool
    calls = []
    def interrupted(request, **options):
        calls.append(request)
        summary = {'ci_status': 'observation_interrupted', 'bundle_number': request.bundle,
                   'evidence_complete': False, 'files': {}}
        return summary, {'summary.json': json.dumps(summary).encode()}
    monkeypatch.setattr(tool, 'observe_ci', interrupted)
    assert tool.main(cli_arguments(tmp_path)) == 0
    assert len(calls) == 1 and calls[0].bundle == 39
    with zipfile.ZipFile(BytesIO(recover_evidence(capsys.readouterr().out))) as archive:
        summary = json.loads(archive.read('summary.json'))
        assert summary['ci_status'] == 'observation_interrupted'
        assert summary['prior_recovery_skipped'] == 'observation_interrupted'
