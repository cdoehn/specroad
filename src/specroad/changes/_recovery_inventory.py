"""Observe complete recovery membership under the journal-bound configuration.

No normal model load, guessed profile selection or new semantic root. Exact
membership and bytes preserve the roots independently checked at publication
preflight. Unreferenced payloads and operational data remain outside the model.
"""
from contextlib import contextmanager
from hashlib import sha256

from ..model.paths import CURRENT_JSON_CLASSES
from ..storage.project import ProjectSource
from ..storage.resource_discovery import current_json_paths
from .recovery_values import RecoveryError


def check_membership(files, journal, *, phase='target'):
    """Prove the complete JSON path set, including permitted rollback creates.

    Non-JSON resources are already explicit journal inputs and must separately
    pass the caller's full byte check. Configuration bytes are proven BEFORE
    their managed paths can influence this inventory.
    """
    if phase not in ('target', 'base', 'intermediate'):
        raise ValueError('Unknown recovery inventory phase')
    data = journal.data
    inventory = {item['path']: item for item in data['target_inventory']}
    configuration = inventory.get('specroad.json')
    if configuration is None:
        raise RecoveryError('recovery_configuration_unbound', path='specroad.json', exit_code=6)
    raw = files.boundary.read_bytes('specroad.json')
    if (len(raw), sha256(raw).hexdigest()) != (configuration['size'], configuration['sha256']):
        raise RecoveryError('recovery_configuration_changed', path='specroad.json', exit_code=6)
    source = ProjectSource(files.boundary.root, expected_project_id=data['project_id'])
    if (source.boundary._root_identity != files.boundary._root_identity
            or source.configuration_bytes != raw):
        raise RecoveryError('recovery_configuration_changed', path='specroad.json', exit_code=6)
    target = {path for path in inventory if source.classify(path) in CURRENT_JSON_CLASSES}
    created = {entry['path'] for entry in data['files'] if not entry['existed_before']}
    basis = target - created
    observed = set(current_json_paths(source))
    required = target if phase == 'target' else basis
    allowed = basis if phase == 'base' else target
    difference = (required - observed) | (observed - allowed)
    if difference:
        raise RecoveryError('recovery_inventory_mismatch', path=sorted(difference)[0], exit_code=6)
    if set(current_json_paths(source)) != observed:
        raise RecoveryError('recovery_inventory_changed', exit_code=6)
    source.check_current()
    files.check_root()
    return tuple(sorted(observed))


@contextmanager
def verified_membership(files, journal, *, phase='target'):
    """Keep the same complete-membership checks around a caller's byte proof."""
    check_membership(files, journal, phase=phase)
    yield
    check_membership(files, journal, phase=phase)
