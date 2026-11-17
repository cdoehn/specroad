"""Recovery rejects foreign inventories and preserves evidence at retry boundaries."""
from hashlib import sha256
import json
import os
from pathlib import Path

import pytest

from specroad.changes import CommittedJournal, CommittingJournal, RecoveryAuthority, RecoveryError, RolledBackJournal, TargetModel, begin_building_journal, inspect_recovery, prepare_publication_check, project_lock, stage_building_journal
from specroad.changes.receipt_projection import prepare_recovery_receipts
from specroad.model.canonical import canonical_json_bytes
from specroad.model.paths import artifact_path
from specroad.validation import ModelDocument
from support.committing import publish
from support.folds import edit, goal
from support.profiles import profile_data
from support.publication import ALLOW, TRANSACTION, options, prepared
from support.recovery import tree
from support.targets import POLICY, plan
from test_publication_check_right import package_model
from support.legacy_publication import crash_after_last_target
from support.legacy_publication import partial_commit


RECOVER = RecoveryAuthority('inventory-test-authorizer', '1', lambda request: True)
ACTIONS = ('complete', 'rollback')
DAMAGE = ('extra_profile', 'extra_artifact', 'missing', 'changed', 'swap', 'configuration')


def _pending(root, action):
    if action == 'complete':
        model, _, _, journal, expected = crash_after_last_target(root)
    else:
        model, _, journal = partial_commit(root)
        expected = model.source_files
    return model, journal, expected






def _damage(root, kind):
    """Change actual resources; return the paths that a diagnosis can identify."""
    profile = root / 'profiles/core.json'
    if kind == 'extra_profile':
        path = 'profiles/additional.json'
        raw = canonical_json_bytes(profile_data(profile_id='additional'))
    elif kind == 'extra_artifact':
        artifact = goal(99)
        path = artifact_path(artifact['artifact_type'], artifact['id'], 'SR')
        raw = canonical_json_bytes(artifact)
    elif kind == 'missing':
        profile.unlink()
        return {'profiles/core.json'}
    elif kind == 'changed':
        raw = profile.read_bytes()
        # Equal length and restored timestamps cannot conceal different bytes.
        stamp = profile.stat()
        profile.write_bytes(bytes((raw[0] ^ 1,)) + raw[1:])
        os.utime(profile, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        return {'profiles/core.json'}
    elif kind == 'swap':
        replacement = root / 'profiles/replaced.json'
        profile.replace(replacement)
        return {'profiles/core.json', 'profiles/replaced.json'}
    elif kind == 'configuration':
        path = 'specroad.json'
        value = json.loads((root / path).read_bytes())
        value['managed_paths'].remove('profiles')
        raw = canonical_json_bytes(value)
    else:
        raise AssertionError(kind)
    destination = root / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    return {path}


def _diagnosis(root):
    return inspect_recovery(root, transaction_id=TRANSACTION,
                            expected_project_id='sample').data












@pytest.mark.parametrize('action', ACTIONS)
@pytest.mark.parametrize('damage', (None, 'extra_profile', 'missing', 'configuration'))
def test_diagnosis_never_loads_canonical_model_or_changes_evidence(tmp_path, monkeypatch, action, damage):
    from specroad.storage import inventory as model_inventory
    from specroad.storage.project import ProjectSource

    _pending(tmp_path, action)
    if damage is not None:
        _damage(tmp_path, damage)
    before = _without_lock(tmp_path)

    def model_load_forbidden(*args, **kwargs):
        raise AssertionError('Recovery attempted canonical model loading')

    monkeypatch.setattr(ProjectSource, 'load_resources', model_load_forbidden)
    monkeypatch.setattr(TargetModel, '__init__', model_load_forbidden)
    monkeypatch.setattr(model_inventory, 'inventory_project', model_load_forbidden)
    status = _diagnosis(tmp_path)
    row = status['transactions'][0]
    assert status['model_loaded'] is False and status['write_authorized'] is False
    assert row['state'] == ('committing' if damage is None else 'corrupt')
    assert row['critical_inputs_verified'] is (damage is None)
    assert _without_lock(tmp_path) == before












def _without_lock(root):
    value = tree(root)
    value.pop('.specroad/locks/project.json', None)
    return value
