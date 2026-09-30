"""Retry GET failures without changing report, run or test-result semantics."""
from copy import deepcopy
from hashlib import sha256
import pytest
from watch_bundle_ci import Request, CIObservationError, observe_ci
from test_ci_wait import SHA, run_value
from test_ci_wait_right import ArtifactClient, SOURCE, report_zip


class Flaky(ArtifactClient):
    def __init__(self, failures=1, *, collection=False):
        super().__init__()
        self.failures, self.collection = failures, collection
        self.gets, self.lists = [], 0
    def get(self, path):
        self.gets.append(path)
        if path.endswith('/artifacts/101/zip') and self.failures:
            self.failures -= 1
            raise CIObservationError('gh_api_exit_1')
        return super().get(path)
    def document(self, path):
        if '/artifacts?' in path:
            self.lists += 1
            if self.collection and self.failures:
                self.failures -= 1
                raise CIObservationError('gh_unavailable_or_api_timeout')
        return super().document(path)


@pytest.mark.parametrize('failures', [1, 2])
def test_same_artifact_retried_then_all_reports_verified(failures):
    client = Flaky(failures)
    sleeps, events = [], []
    summary, files = observe_ci(Request(SHA, 22, SOURCE, event='push', expected_mode='parallel'), client=client,
        sleeper=sleeps.append, progress=events.append)
    assert summary['ci_status'] == 'success'
    assert summary['evidence_complete'] and summary['test_evidence_verified']
    assert files['reports-3.10.zip'] == client.archives[101]
    assert len([p for p in client.gets if p.endswith('/artifacts/101/zip')]) == failures+1
    assert len(sleeps) == failures
    assert len([e for e in events if e['phase'] == 'retry']) == failures


def test_exhausted_artifact_get_keeps_other_reports_and_actual_ci_status():
    client = Flaky(50); sleeps = []
    summary, files = observe_ci(Request(SHA, 22, SOURCE, event='push', expected_mode='parallel'),client=client,sleeper=sleeps.append)
    assert summary['ci_status'] == 'success' and not summary['evidence_complete']
    assert not summary['test_evidence_verified']
    assert len(summary['test_reports']) == 4 and 'reports-3.10.zip' not in files
    assert 'logs.zip' in files and len(sleeps) == 2
    assert len([p for p in client.gets if p.endswith('/artifacts/101/zip')]) == 3
    assert summary['errors'][0]['python'] == '3.10'


def test_artifact_collection_retried_without_duplicating_entries():
    client = Flaky(2, collection=True)
    summary, files = observe_ci(Request(SHA, 22, SOURCE, event='push', expected_mode='parallel'),client=client,sleeper=lambda _:None)
    assert client.lists == 3 and summary['evidence_complete']
    assert len(summary['test_reports']) == 5


def test_exhausted_collection_marks_observation_unavailable():
    client = Flaky(50, collection=True)
    summary,files = observe_ci(Request(SHA,22,SOURCE, event='push', expected_mode='parallel'),client=client,sleeper=lambda _:None)
    assert summary['ci_status'] == 'unavailable' and client.lists == 3
    assert 'logs.zip' in files and not summary['test_evidence_verified']


@pytest.mark.parametrize('corrupt', ['digest', 'report', 'zip'])
def test_successful_get_with_invalid_bytes_is_not_retried(corrupt):
    client=Flaky(0)
    if corrupt=='digest': client.artifacts[0]['digest']='sha256:'+'0'*64
    else:
        raw=report_zip(changes={'suite_passed':False}) if corrupt=='report' else b'not a zip'
        client.archives[101]=raw
        client.artifacts[0]['digest']='sha256:'+sha256(raw).hexdigest()
    summary,files=observe_ci(Request(SHA,22,SOURCE, event='push', expected_mode='parallel'),client=client,sleeper=lambda _:None)
    assert not summary['test_evidence_verified']
    assert len([p for p in client.gets if p.endswith('/artifacts/101/zip')]) == 1
    assert len(summary['test_reports']) == 4


def test_retry_cannot_hide_changed_run_attempt():
    class Changed(Flaky):
        def document(self,path):
            if path.endswith('/runs/51') and self.gets:
                return run_value(run_attempt=2)
            return super().document(path)
    summary,_=observe_ci(Request(SHA,22,SOURCE, event='push', expected_mode='parallel'),client=Changed(1),sleeper=lambda _:None)
    assert summary['ci_status']=='unavailable' and not summary['test_evidence_verified']
    assert summary['errors'][-1]['reason']=='run_attempt_changed'


def test_interrupt_during_retry_does_not_continue_or_cancel_ci():
    def interrupt(_): raise KeyboardInterrupt()
    client=Flaky(3)
    summary,files=observe_ci(Request(SHA,22,SOURCE, event='push', expected_mode='parallel'),client=client,sleeper=interrupt)
    assert summary['ci_status']=='observation_interrupted'
    assert not summary['evidence_complete']
    assert len([p for p in client.gets if p.endswith('/artifacts/101/zip')]) == 1
    assert all('/rerun' not in p and '/cancel' not in p for p in client.gets)


def test_failed_test_verdict_is_never_retried_as_an_api_failure():
    client=Flaky(1);client.run=run_value(conclusion='failure')
    # Client stores the run as run, retaining the upstream fixture contract.
    summary,_=observe_ci(Request(SHA,22,SOURCE, event='push', expected_mode='parallel'),client=client,sleeper=lambda _:None)
    assert summary['ci_status'] == 'failed'
