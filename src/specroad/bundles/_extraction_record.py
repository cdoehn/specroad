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


def restore_inventory(tree, raw, content, directories):
    value = parse_json_object(raw)
    fields = {'format', 'state', 'root_identity', 'root_created', 'stage_identity',
              'units', 'reused_directories', 'entries'}
    def require(condition):
        if not condition:
            raise BootstrapError('bundle_bootstrap_journal_invalid')
    require(set(value) == fields and canonical_json_bytes(value) == raw)
    require(value['format'] == FORMAT and value['state'] == 'prepared')
    require(type(value['root_created']) is bool and value['reused_directories'] == {})
    require(value['root_identity'] == identity(os.fstat(tree.held.root_fd)))
    require(value['stage_identity'] == tree.stage_identity)
    entries = value['entries']
    require(type(entries) is dict and set(entries) == set(content) | directories)
    tokens = {_identity(value['root_identity']), _identity(value['stage_identity'])}
    require(len(tokens) == 2)
    for path, item in entries.items():
        token = _metadata(item, 'directory' if path in directories else 'file')
        require(token not in tokens)
        tokens.add(token)
        if path in content:
            from hashlib import sha256
            require(item['size'] == len(content[path]) and item['sha256'] == sha256(content[path]).hexdigest())
    units = sorted(p for p in entries if '/' not in p)
    units.remove('specroad.json'); units.append('specroad.json')
    require(value['units'] == units)
    tree.inventory = entries
    tree.units = units
