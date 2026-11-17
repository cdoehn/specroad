"""Complete original proofs, separate roots and retained failures at Git restart."""
import pytest

from specroad.changes import transaction_preflight
from specroad.changes.receipt_values import request_receipt_path, transaction_receipt_path
from specroad.cli.contracts import CommandClass
from specroad.model.errors import ModelError
from specroad.bundles.errors import BundleError
from specroad.qualification import QualificationServices
from specroad.qualification.project import validate_project
from support.git_restart import project_files, save, checkout, new_write
from support.proposal_apply import ApplyCase
from support.read_only import inventory, no_write_attempts
from test_git_restart import saved_project, interrupted


def test_absent_optional_request_history_starts_new_intent_without_replaying_old(tmp_path):
    root = tmp_path / 'source'; commit, original = saved_project(root)
    fresh = checkout(root, tmp_path / 'fresh', commit)
    # Explicit user-selected snapshot with no optional local request history.
    for name in original:
        if name.startswith('.specroad/'):
            (fresh / name).unlink()
    with no_write_attempts():
        validate_project(project_files(fresh))
    result = new_write(fresh, 'brand-new-request', 'brand-new-transaction', 'New local history')
    assert result['commit_completed'] and not result['replayed']
    assert not (fresh / request_receipt_path('saved-request')).exists()
    assert (fresh / request_receipt_path('brand-new-request')).is_file()
    assert project_files(root) == original


@pytest.mark.parametrize('effect', ['read', 'plan', 'dry-run', 'write'])
def test_a_git_copy_of_active_interruption_data_remains_blocked(tmp_path, monkeypatch, effect):
    root = tmp_path / 'source'; saved_project(root); interrupted(root, monkeypatch)
    commit, damaged = save(root)  # Deliberately invalid user-selected snapshot.
    fresh = checkout(root, tmp_path / 'invalid', commit)
    before = inventory(fresh)
    command = {'read': CommandClass.READ_ONLY, 'plan': CommandClass.PLAN_OUTPUT,
               'dry-run': CommandClass.NORMATIVE_WRITE, 'write': CommandClass.NORMATIVE_WRITE}[effect]
    with no_write_attempts():
        result = transaction_preflight(fresh, command_class=command, dry_run=effect == 'dry-run')
    assert result.exit_code == 5 and result.data['project_corrupted']
    assert not result.data['normal_operation_started'] and not result.data['mutation_possible']
    assert inventory(fresh) == before and project_files(root) == damaged


@pytest.mark.parametrize('missing', [None, 'request', 'transaction'])
def test_applied_proposal_requires_original_native_receipts_in_the_new_root(tmp_path, missing):
    source = tmp_path / 'source'; case = ApplyCase(source); result = case.apply()
    assert result['completion']['current_target_verified']
    commit, saved = save(source); fresh = checkout(source, tmp_path / 'fresh', commit)
    if missing is not None:
        name = (request_receipt_path('synthetic-apply-request') if missing == 'request'
                else transaction_receipt_path('synthetic-apply'))
        (fresh / name).unlink()
    case.root = fresh
    before = inventory(fresh)
    with no_write_attempts():
        if missing is None:
            inputs, model = case.completion_inputs()
            services = QualificationServices(proposal_inputs=lambda snapshot, original: inputs)
            checked, _ = validate_project(project_files(fresh), services=services)
            assert checked.source_files == model.source_files
        else:
            # This is the real proof reader, not a provider returning guessed success.
            with pytest.raises((ModelError, BundleError)):
                case.completion_inputs()
            with pytest.raises((ModelError, BundleError)):
                validate_project(project_files(fresh), services=case.services)
    assert inventory(fresh) == before and project_files(source) == saved


@pytest.mark.parametrize('missing', [False, True])
def test_referenced_archive_object_is_required_in_a_separate_checkout(tmp_path, missing):
    from support.restore import restore_case
    from support.records import record_value
    from support.domain import domain_value
    options, _, _ = restore_case(tmp_path, 'baseline', values=[record_value('document'),
        record_value('configuration'), domain_value('goal')])
    source = options['source_root']
    commit, saved = save(source); fresh = checkout(source, tmp_path / 'fresh', commit)
    objects = sorted(p for p in saved if p.startswith('archive/objects/'))
    assert objects
    if missing:
        (fresh / objects[0]).unlink()
    before = inventory(fresh)
    with no_write_attempts():
        if missing:
            with pytest.raises((ModelError, BundleError)):
                validate_project(project_files(fresh))
        else:
            validate_project(project_files(fresh))
    assert inventory(fresh) == before and project_files(source) == saved
