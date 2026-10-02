"""Complete recovery membership and byte binding, independent of journal selection.

Expected roots come from the already checked model/plan before recovery. These
tests establish transitive binding through complete path and byte equality; they
do not claim that recovery recomputes the semantic model root.
"""
import json
from pathlib import Path

import pytest

from specroad.changes import RecoveryError, RolledBackJournal
from specroad.model.canonical import canonical_json_bytes
from specroad.model.paths import artifact_path
from support.folds import goal
from support.publication import files
from support.recovery import tree
from test_transaction_recovery_completion import (
    crash_after_last_target,
    recover as complete,
)
from test_transaction_recovery_rollback import (
    partial_commit,
    recover as rollback,
)


def extra_goal(root):
    """A real valid normative artifact, not malformed bytes or an unknown suffix."""
    value = goal(9)
    logical = artifact_path(value['artifact_type'], value['id'], 'SR')
    path = Path(root, logical)
    assert not path.exists()
    raw = canonical_json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return logical, raw


def expected_target(model, plan, preflight):
    """Use independently prepared source/request bytes, never target_inventory."""
    documents = preflight.request.documents
    expected = {
        **model.source_files,
        **{document.path: document.content for document in documents},
    }
    artifact_paths = {document.path for document in model.documents}
    artifact_paths.update(document.path for document in documents)
    artifacts = [json.loads(expected[path]) for path in sorted(artifact_paths)]
    root = model.manifest(artifacts, plan.data['base']['scope_descriptor']).sha256
    assert root == plan.data['expected_result']['model_root_sha256']
    return expected, root


def expected_basis(model, plan):
    expected = dict(model.source_files)
    root = model.manifest(
        model.artifacts, plan.data['base']['scope_descriptor']
    ).sha256
    assert root == plan.data['base']['model_root_sha256']
    return expected, root


def test_completion_rejects_additional_valid_normative_artifact(tmp_path):
    model, plan, preflight, journal, _ = crash_after_last_target(tmp_path)
    expected, _ = expected_target(model, plan, preflight)
    assert files(tmp_path) == expected
    logical, raw = extra_goal(tmp_path)
    before = tree(tmp_path)

    with pytest.raises(RecoveryError) as error:
        complete(tmp_path, journal)

    assert error.value.exit_code == 6
    assert not error.value.mutation_possible
    assert error.value.normative_writes_by_recovery == 0
    assert tree(tmp_path) == before
    assert Path(tmp_path, logical).read_bytes() == raw
    assert not Path(tmp_path, '.specroad/requests').exists()
    assert not Path(tmp_path, '.specroad/transactions/receipts').exists()


def test_rollback_rejects_additional_valid_normative_artifact_before_restoration(tmp_path):
    model, plan, journal = partial_commit(tmp_path)
    basis, _ = expected_basis(model, plan)
    assert files(tmp_path) != basis
    logical, raw = extra_goal(tmp_path)
    before = tree(tmp_path)

    with pytest.raises(RecoveryError) as error:
        rollback(tmp_path, journal)

    assert error.value.exit_code == 6
    assert not error.value.mutation_possible
    assert error.value.normative_writes_by_recovery == 0
    assert tree(tmp_path) == before
    assert Path(tmp_path, logical).read_bytes() == raw
    assert Path(tmp_path, journal.path).read_bytes() == journal.source_bytes


def test_rolled_back_retry_rechecks_complete_normative_membership(tmp_path):
    model, plan, journal = partial_commit(tmp_path)
    basis, root = expected_basis(model, plan)
    first = rollback(tmp_path, journal)
    assert first.data['rollback_completed']
    assert first.data['base_model_root_sha256'] == root
    assert files(tmp_path) == basis
    terminal = RolledBackJournal(Path(tmp_path, journal.path).read_bytes())
    logical, raw = extra_goal(tmp_path)
    before = tree(tmp_path)

    with pytest.raises(RecoveryError) as error:
        rollback(tmp_path, terminal)

    assert error.value.exit_code == 6
    assert not error.value.mutation_possible
    assert error.value.normative_writes_by_recovery == 0
    assert tree(tmp_path) == before
    assert Path(tmp_path, logical).read_bytes() == raw


def test_completion_matches_independently_bound_full_target_bytes_and_root(tmp_path):
    model, plan, preflight, journal, _ = crash_after_last_target(tmp_path)
    target, root = expected_target(model, plan, preflight)
    assert target != model.source_files
    assert files(tmp_path) == target

    result = complete(tmp_path, journal).data

    assert result['commit_completed'] and result['current_target_verified']
    assert result['target_model_root_sha256'] == root
    assert result['normative_writes'] == 0
    assert files(tmp_path) == target


def test_rollback_matches_independently_bound_full_basis_bytes_and_root(tmp_path):
    model, plan, journal = partial_commit(tmp_path)
    basis, root = expected_basis(model, plan)
    assert files(tmp_path) != basis

    result = rollback(tmp_path, journal).data

    assert result['rollback_completed'] and result['state'] == 'rolled_back'
    assert result['base_model_root_sha256'] == root
    assert result['normative_writes'] > 0
    assert files(tmp_path) == basis


@pytest.mark.parametrize('action', ['completion', 'rollback'])
def test_unreferenced_and_operational_files_survive_recovery_unchanged(tmp_path, action):
    if action == 'completion':
        model, plan, preflight, journal, _ = crash_after_last_target(tmp_path)
        expected, root = expected_target(model, plan, preflight)
        run = complete
    else:
        model, plan, journal = partial_commit(tmp_path)
        expected, root = expected_basis(model, plan)
        run = rollback
    unrelated = {
        'attachments/unreferenced.bin': b'unreferenced attachment\x00\xff',
        'generated/unrelated.json': b'not normative JSON',
        '.specroad/cache/unrelated.bin': b'operational bytes',
        'archive/objects/ab/' + 'ab' * 32: b'archived bytes',
    }
    for logical, raw in unrelated.items():
        path = Path(tmp_path, logical)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    result = run(tmp_path, journal).data

    if action == 'completion':
        assert result['commit_completed'] and result['current_target_verified']
        assert result['target_model_root_sha256'] == root
        assert result['normative_writes'] == 0
    else:
        assert result['rollback_completed']
        assert result['base_model_root_sha256'] == root
    assert all(Path(tmp_path, logical).read_bytes() == raw
               for logical, raw in unrelated.items())
    assert files(tmp_path) == {
        **expected,
        **{logical: raw for logical, raw in unrelated.items()
           if not logical.startswith('.specroad/')},
    }
