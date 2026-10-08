"""Exact configuration alternatives for recovery of a byte-only normalization.

An unchanged configuration keeps its old exact target binding. A changed one
requires the operation's two hashes and independently retained target bytes;
arbitrary canonical-equivalent live bytes are never a permitted alternative.
"""
from hashlib import sha256
from ..model.representation import normal_json_bytes
from ..model.errors import ModelError
from ._discard_basis_contract import staging_images
from .recovery_values import RecoveryError


def configuration_normalization(journal):
    data = journal.data
    entry = next((e for e in data['files'] if e['path'] == 'specroad.json'), None)
    if entry is None:
        return None
    operations = data['authoring_binding']['operations']
    selected = [op for op in operations if op.get('path') == 'specroad.json']
    if (not entry['existed_before'] or len(selected) != 1 or
            any(op['op'] != 'representation_normalize' for op in operations) or
            selected[0]['expected_byte_sha256'] != entry['before_sha256'] or
            selected[0]['target_byte_sha256'] != entry['after_sha256']):
        raise RecoveryError('recovery_configuration_normalization_unbound', exit_code=6)
    try:
        target = staging_images(data.get('discard_basis', {})).get('specroad.json')
        if (target is None or (len(target), sha256(target).hexdigest()) !=
                (entry['after_size'], entry['after_sha256']) or normal_json_bytes(target) != target):
            raise RecoveryError('recovery_configuration_normalization_unbound', exit_code=6)
    except ModelError as error:
        raise RecoveryError('recovery_configuration_normalization_unbound', exit_code=6) from error
    return entry, target


def check_configuration(raw, journal, *, phase):
    data = journal.data
    configuration = next((e for e in data['target_inventory'] if e['path'] == 'specroad.json'), None)
    if configuration is None:
        raise RecoveryError('recovery_configuration_unbound', path='specroad.json', exit_code=6)
    actual = len(raw), sha256(raw).hexdigest()
    normalized = configuration_normalization(journal)
    if normalized is None:
        allowed = {(configuration['size'], configuration['sha256'])}
    else:
        entry, target = normalized
        before = entry['before_size'], entry['before_sha256']
        after = entry['after_size'], entry['after_sha256']
        if (configuration['size'], configuration['sha256']) != after:
            raise RecoveryError('recovery_configuration_normalization_unbound', exit_code=6)
        allowed = {before} if phase == 'base' else {after} if phase == 'target' else {before, after}
        if actual in allowed:
            try:
                if normal_json_bytes(raw) != target:
                    raise RecoveryError('recovery_configuration_values_changed', exit_code=6)
            except ModelError as error:
                raise RecoveryError('recovery_configuration_values_changed', exit_code=6) from error
    if actual not in allowed:
        raise RecoveryError('recovery_configuration_changed', path='specroad.json', exit_code=6)
