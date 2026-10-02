"""Malformed selection or revision metadata must never silently run/pass CI."""
from types import SimpleNamespace
import subprocess
import pytest
from verification_support.bundle_ci import select_ci, bundle_metadata
from select_bundle_ci import resolve_selection
from test_bundle_ci import SHA, message


@pytest.mark.parametrize('number', ['000', '09', '0009', '-01', 'abc', '9999999999'])
def test_invalid_bundle_numbers(number):
    with pytest.raises(ValueError): bundle_metadata(message().replace('009',number))


@pytest.mark.parametrize('trailer', ['SpecRoad-Bundle: 010', 'SpecRoad-Bundle-Final: false'])
def test_duplicates_even_if_last_value_would_be_usable(trailer):
    with pytest.raises(ValueError): bundle_metadata(message()+'\n'+trailer)


@pytest.mark.parametrize('event', ['pull_request', 'pull_request_target', '', None])
def test_unknown_events_are_rejected_before_git(event):
    calls=[]
    with pytest.raises(ValueError):
        resolve_selection({'GITHUB_EVENT_NAME':event, 'GITHUB_SHA':SHA},runner=lambda *a,**k:calls.append(a))
    assert not calls


def test_push_cannot_override_target_revision():
    with pytest.raises(ValueError): resolve_selection({'GITHUB_EVENT_NAME':'push','SR_COMMIT_SHA':SHA})


def test_manual_legacy_modes_resolve_to_parallel():
    result=select_ci('workflow_dispatch','refs/heads/dev',SHA,message(20),mode='auto')
    assert result['mode']=='parallel'
    assert select_ci('workflow_dispatch','refs/heads/dev',SHA,message(20),mode='parallel')['mode'] == 'parallel'


def test_fifth_bundle_intermediate_is_still_manual_only():
    result=select_ci('push','refs/heads/dev',SHA,message(20,False))
    assert result['run_full'] is False


def test_failure_to_prove_dev_ancestry_stops_selection():
    calls=[]
    def runner(cmd,**kw):
        calls.append(cmd)
        if cmd[1]=='merge-base':raise subprocess.CalledProcessError(1,cmd)
        return SimpleNamespace(stdout=(SHA+'\n').encode())
    with pytest.raises(subprocess.CalledProcessError):
        resolve_selection({'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_SHA':SHA, 'GITHUB_REF':'refs/heads/dev', 'SR_CI_RUNNER':'github-hosted'},runner=runner)
    assert len(calls)==2


def test_resolved_revision_cannot_change():
    with pytest.raises(ValueError):
        resolve_selection({'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_SHA':SHA, 'GITHUB_REF':'refs/heads/dev', 'SR_CI_RUNNER':'github-hosted'},
                          runner=lambda *a,**k:SimpleNamespace(stdout=b'b'*40+b'\n'))


def test_manual_without_sha_uses_event_revision_not_moving_dev_tip():
    def runner(cmd,**kw):
        return SimpleNamespace(stdout=(SHA+'\n' if cmd[1]=='rev-parse' else message() if cmd[1]=='show' else '').encode())
    assert resolve_selection({'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_SHA':SHA, 'GITHUB_REF':'refs/heads/dev', 'SR_CI_RUNNER':'github-hosted'},runner=runner)['commit_sha']==SHA
