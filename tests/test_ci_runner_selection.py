"""Runner/API/scheduling data contracts, not workflow text or terminal layout."""
from copy import deepcopy
import json
import pytest
from ci_support.runners import (NAME, SELF_HOSTED, HOSTED, choose_runner,
    probe_runner, commit_runner, runner_labels, terminal_ci_status)
from ci_support.contract import CIObservationError
from select_bundle_ci import resolve_selection
from test_bundle_ci import SHA, message
from types import SimpleNamespace


def candidate(**changes):
    value = {'id': 17, 'name': NAME, 'status': 'online', 'busy': False,
             'labels': [{'name': label} for label in SELF_HOSTED]}
    value.update(changes)
    return value


def test_only_online_idle_exact_hetzner_is_primary():
    assert choose_runner([candidate()]) == ('hetzner', 'hetzner_online_idle', 17)
    assert runner_labels('hetzner') == list(SELF_HOSTED)
    assert runner_labels('github-hosted') == list(HOSTED)


@pytest.mark.parametrize('changes', [dict(status='offline'), dict(busy=True), dict(busy=None),
    dict(labels=[{'name': 'self-hosted'}]), dict(labels=None), dict(id=True),
    dict(name='Blade-15'), dict(name='other-hetzner')])
def test_unavailable_mislabelled_or_old_runner_falls_back(changes):
    assert choose_runner([candidate(**changes)])[0] == 'github-hosted'


def test_empty_or_ambiguous_candidate_falls_back():
    assert choose_runner([])[0] == 'github-hosted'
    assert choose_runner([candidate(), candidate(id=18)])[0] == 'github-hosted'


def test_old_runner_cannot_override_a_good_hetzner():
    assert choose_runner([candidate(name='Blade-15'), candidate()])[0] == 'hetzner'


def test_api_failure_falls_back_without_leaking_credentials():
    class Client:
        def document(self, path):
            raise CIObservationError('secret credential diagnostic')
    value = probe_runner(client=Client())
    assert value['choice'] == 'github-hosted'
    assert value['reason'] == 'runner_query_unavailable'
    assert 'secret' not in json.dumps(value)


def test_probe_is_read_only_and_paginates_all_candidates():
    class Client:
        def __init__(self): self.calls=[]
        def document(self, path):
            self.calls.append(path)
            return {'total_count': 2, 'runners': [candidate(name='Blade-15', id=16)]
                if path.endswith('&page=1') else [candidate()]}
    client=Client(); result=probe_runner(client=client)
    assert result['choice']=='hetzner' and result['reservation'] is False
    assert len(client.calls)==2 and all('/actions/runners?' in p for p in client.calls)


@pytest.mark.parametrize('value', ['blade', '', 'hetzner,ubuntu-24.04', None])
def test_unknown_runner_never_becomes_a_label_expression(value):
    with pytest.raises(ValueError): runner_labels(value)


def test_trailer_must_be_unambiguous():
    assert commit_runner('old commit') == 'github-hosted'
    assert commit_runner('SpecRoad-CI-Runner: hetzner\n') == 'hetzner'
    with pytest.raises(ValueError): commit_runner('SpecRoad-CI-Runner: blade')
    with pytest.raises(ValueError): commit_runner('SpecRoad-CI-Runner: hetzner\nSpecRoad-CI-Runner: github-hosted')


@pytest.mark.parametrize('choice', ['hetzner', 'github-hosted'])
def test_selection_passes_an_actual_runner_alternative(choice):
    def git(cmd, **kwargs):
        text = SHA+'\n' if cmd[1]=='rev-parse' else (message(38)+'SpecRoad-CI-Runner: '+choice+'\n') if cmd[1]=='show' else ''
        return SimpleNamespace(stdout=text.encode())
    value=resolve_selection({'GITHUB_EVENT_NAME':'push','GITHUB_SHA':SHA,'GITHUB_REF':'refs/heads/dev'},runner=git)
    assert json.loads(value['runner'])==runner_labels(choice)
    assert value['run_full'] and value['mode']=='parallel'


def test_manual_historical_revision_does_not_inherit_a_stale_hetzner_probe():
    def git(cmd, **kwargs):
        text = SHA+'\n' if cmd[1]=='rev-parse' else message(38)+'SpecRoad-CI-Runner: hetzner\n' if cmd[1]=='show' else ''
        return SimpleNamespace(stdout=text.encode())
    env={'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_SHA':SHA,'GITHUB_REF':'refs/heads/dev'}
    value=resolve_selection(env, runner=git)
    assert json.loads(value['runner'])==list(HOSTED)


@pytest.mark.parametrize('status,expected', [('success','SUCCESS'),('failed','FAILED'),('cancelled','CANCELLED'),
    ('not_published','UNAVAILABLE'),('incomplete','UNAVAILABLE'),('observation_interrupted','UNAVAILABLE'),
    ('unavailable','UNAVAILABLE')])
def test_terminal_status_never_conflates_local_and_ci(status,expected):
    assert terminal_ci_status(status)==expected
