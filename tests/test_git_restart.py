"""A separate complete Git checkout is usable; no product repair is performed."""

import pytest

from specroad.changes import guarded_write, transaction_preflight, read_guarded_completion
from specroad.changes.receipt_values import transaction_receipt_path, request_receipt_path
from specroad.cli.contracts import CommandClass
from specroad.model.errors import ModelError
from specroad.bundles.errors import BundleError
from specroad.qualification.project import validate_project
from support.domain import domain_value
from support.git_restart import project_files, save, checkout, new_write
from support.read_only import inventory, no_write_attempts
from support.records import record_value
from test_proposal_basis import project


def saved_project(root):
    project(root, artifacts=[domain_value('goal'), record_value('configuration'),
                             record_value('document')])
    result = new_write(root, 'saved-request', 'saved-transaction', 'Saved valid statement')
    assert result['commit_completed']
    commit, files = save(root)
    with no_write_attempts():
        validate_project(files)
    return commit, files


def interrupted(root, monkeypatch):
    reached = []
    def stop(event):
        if event == 'effect_replaced:0':
            reached.append(event)
            raise OSError(5, 'Owned interruption after a real file replacement')
    with monkeypatch.context() as patch:
        patch.setattr(guarded_write, '_checkpoint', stop)
        with pytest.raises(ModelError):
            new_write(root, 'interrupted-request', 'interrupted-transaction', 'Interrupted statement')
    assert reached == ['effect_replaced:0']
    (root / 'untracked-user-file.bin').write_bytes(b'keep original user bytes\0\xff')
    assert transaction_preflight(root, command_class=CommandClass.READ_ONLY).exit_code == 5


def test_complete_separate_checkout_accepts_new_intent_and_retains_old_root(tmp_path, monkeypatch):
    root = tmp_path / 'damaged'; commit, saved = saved_project(root)
    interrupted(root, monkeypatch)
    damaged = inventory(root)
    fresh = checkout(root, tmp_path / 'fresh', commit)
    assert project_files(fresh) == saved
    assert fresh.stat().st_ino != root.stat().st_ino
    assert not (fresh / 'untracked-user-file.bin').exists()
    with no_write_attempts():
        validate_project(project_files(fresh))
        historical = read_guarded_completion(fresh, 'saved-transaction', expected_project_id='sample').data
    assert historical['replayed'] and not historical['current_target_verified']
    before_receipts = {p: raw for p, raw in saved.items() if p.startswith('.specroad/')}
    result = new_write(fresh, 'fresh-intent', 'fresh-transaction', 'New explicit intent')
    assert result['commit_completed'] and not result['replayed']
    assert before_receipts.items() <= project_files(fresh).items()
    assert (fresh / request_receipt_path('fresh-intent')).is_file()
    assert not (fresh / request_receipt_path('interrupted-request')).exists()
    assert inventory(root) == damaged
    with no_write_attempts():
        blocked = transaction_preflight(root, command_class=CommandClass.NORMATIVE_WRITE)
    assert blocked.exit_code == 5 and blocked.data['reason'] == 'project_corrupted'
    assert inventory(root) == damaged


@pytest.mark.parametrize('missing', ['specroad.json', 'profile', 'transaction', 'request'])
def test_incomplete_checkout_fails_native_qualification_without_reconstruction(tmp_path, missing):
    root = tmp_path / 'source'; commit, saved = saved_project(root)
    fresh = checkout(root, tmp_path / 'incomplete', commit)
    path = ('specroad.json' if missing == 'specroad.json' else 'profiles/core.json' if missing == 'profile'
            else transaction_receipt_path('saved-transaction') if missing == 'transaction'
            else request_receipt_path('saved-request'))
    (fresh / path).unlink()
    before = inventory(fresh)
    with no_write_attempts(), pytest.raises((ModelError, BundleError)):
        validate_project(project_files(fresh))
    assert inventory(fresh) == before and project_files(root) == saved
