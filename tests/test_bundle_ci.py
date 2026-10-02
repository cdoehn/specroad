"""Test scheduling decisions and exact revision resolution, not YAML wording."""
import copy
from types import SimpleNamespace
import pytest
from verification_support.bundle_ci import bundle_metadata, select_ci, commit_sha
from select_bundle_ci import resolve_selection

SHA = 'a' * 40

def message(number=9, final=True):
    return f'feat: example\n\nSpecRoad-Bundle: {number:03d}\nSpecRoad-Bundle-Final: {str(final).lower()}\n'


def test_final_dev_commit_never_starts_automatic_full_tests():
    assert select_ci('push', 'refs/heads/dev', SHA, message())['mode'] == 'parallel'
    assert select_ci('push', 'refs/heads/dev', SHA, message())['run_full'] is False


def test_intermediate_commit_has_no_automatic_full_run():
    assert select_ci('push', 'refs/heads/dev', SHA, message(final=False))['run_full'] is False


def test_main_does_not_trigger_product_ci():
    assert select_ci('push', 'refs/heads/main', SHA, message())['run_full'] is False


def test_manual_intermediate_runs_both_full_modes():
    assert select_ci('workflow_dispatch', 'refs/heads/dev', SHA, message(final=False))['run_full'] is True


def test_fifth_bundle_numbers_do_not_trigger_full_tests():
    for number in (5, 10, 15, 20, 25, 1000):
        assert select_ci('push', 'refs/heads/dev', SHA, message(number))['run_full'] is False


def test_manual_other_final_bundles_also_use_both():
    for number in (9, 11, 12, 13, 16, 19, 24):
        assert select_ci('workflow_dispatch', 'refs/heads/dev', SHA, message(number))['mode'] == 'parallel'


def test_unmarked_push_has_no_automatic_full_run():
    assert select_ci('push', 'refs/heads/dev', SHA, 'ordinary commit')['run_full'] is False


def test_manual_historical_commit_is_supported():
    result = select_ci('workflow_dispatch', 'refs/heads/dev', SHA, 'ordinary commit')
    assert result['run_full'] and result['bundle_number'] is None


def test_manual_can_request_both():
    assert select_ci('workflow_dispatch', 'refs/heads/dev', SHA, message(9, False), mode='both')['mode'] == 'parallel'


def test_full_sha_is_required():
    for value in ('a'*7, 'A'*40, '--all', SHA+';echo bad', '', None):
        with pytest.raises(ValueError): commit_sha(value)


def test_ambiguous_trailers_rejected():
    for bad in (message()+'SpecRoad-Bundle: 009\n', 'SpecRoad-Bundle: 009', message().replace('true','maybe')):
        with pytest.raises(ValueError): bundle_metadata(bad)


def test_resolver_passes_exact_sha_without_shell():
    env = {'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REF':'refs/heads/dev',
           'GITHUB_SHA':'b'*40, 'SR_COMMIT_SHA':SHA, 'SR_CI_MODE':'auto', 'SR_CI_RUNNER':'github-hosted'}
    before = copy.deepcopy(env); calls = []
    def runner(cmd, **kwargs):
        calls.append((cmd,kwargs))
        data = SHA+'\n' if cmd[1] == 'rev-parse' else message(final=False) if cmd[1]=='show' else ''
        return SimpleNamespace(stdout=data.encode())
    result = resolve_selection(env, runner=runner)
    assert result['commit_sha'] == SHA and result['run_full']
    assert env == before
    assert calls[1][0] == ['git','merge-base','--is-ancestor',SHA,'origin/dev']
    assert all('shell' not in kw and 'timeout' not in kw for cmd,kw in calls)
