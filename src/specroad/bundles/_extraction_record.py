"""Closed recovery proof for a caller-supplied, independently verified bundle.

Stored paths never select payloads or authorize deletion. The verified container
supplies the complete expected inventory; the journal only binds owned inodes.
"""
import os

from ..authoring._bootstrap_io import BootstrapError, identity
from ..authoring._bootstrap_record import _identity, _metadata
from ..model.canonical import canonical_json_bytes
from ..storage.json_syntax import parse_json_object

COMPLETED = ('.specroad', 'recovery', 'bundle-bootstrap')
FORMAT = 'specroad-bundle-bootstrap-v1'


def checked_inventory(raw, *, root_identity, stage_identity, inventory):
    """Check the local proof against an independently bound file inventory.

    Historical consumers may check selected immutable files later; this does not
    assert that every original normative payload is still the current model.
    """
    value = parse_json_object(raw)
    fields = {'format', 'state', 'root_identity', 'root_created', 'stage_identity',
              'units', 'reused_directories', 'entries'}
    def require(condition):
        if not condition:
            raise BootstrapError('bundle_bootstrap_journal_invalid')
    require(set(value) == fields and canonical_json_bytes(value) == raw)
    require(value['format'] == FORMAT and value['state'] == 'prepared')
    require(type(value['root_created']) is bool and value['reused_directories'] == {})
    require(value['root_identity'] == root_identity)
    require(value['stage_identity'] == stage_identity)
    directories = {'.specroad', '.specroad/recovery'}
    for path in inventory:
        parts = path.split('/')
        directories.update('/'.join(parts[:n]) for n in range(1, len(parts)))
    entries = value['entries']
    require(type(entries) is dict and set(entries) == set(inventory) | directories)
    tokens = {_identity(value['root_identity']), _identity(value['stage_identity'])}
    require(len(tokens) == 2)
    for path, item in entries.items():
        token = _metadata(item, 'directory' if path in directories else 'file')
        require(token not in tokens)
        tokens.add(token)
        if path in inventory:
            require(item['size'] == inventory[path]['size'] and item['sha256'] == inventory[path]['sha256'])
    units = sorted(p for p in entries if '/' not in p)
    units.remove('specroad.json'); units.append('specroad.json')
    require(value['units'] == units)
    return entries, units


def restore_inventory(tree, raw, content, directories):
    from hashlib import sha256
    inventory = {p: {'size': len(b), 'sha256': sha256(b).hexdigest()} for p, b in content.items()}
    entries, units = checked_inventory(raw, root_identity=identity(os.fstat(tree.held.root_fd)),
                                      stage_identity=tree.stage_identity, inventory=inventory)
    if set(entries) != set(content) | directories:
        raise BootstrapError('bundle_bootstrap_journal_invalid')
    tree.inventory, tree.units = entries, units
