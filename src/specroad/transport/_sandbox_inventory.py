"""Read and validate only independently bound native bootstrap inventory.

This module performs no publication or cleanup. Original package bytes select
the complete expected tree; journals bind actual file identities, not authority.
"""
from hashlib import sha256
import os

from ..authoring._bootstrap_io import BootstrapError, STAGING, directory, identity, info_at, metadata
from ..authoring._bootstrap_record import _identity, _metadata
from ..authoring._bootstrap_recovery import _read
from ..bundles._extraction_record import COMPLETED as PROJECT_COMPLETED, checked_inventory
from ..bundles.extraction import _directories
from ..bundles.manifest import MANIFEST_NAME
from ..model.canonical import canonical_json_bytes
from ..storage.json_syntax import parse_json_object

COMPLETED = ('.specroad', 'recovery', 'sandbox-bootstrap')
FORMAT = 'specroad-ai-sandbox-bootstrap-v1'
PROJECT_RECORD = '/'.join((*PROJECT_COMPLETED, 'journal.json'))


def _require(condition):
    if not condition:
        raise BootstrapError('sandbox_bootstrap_inventory_invalid')

def _project_content(container):
    return {**container.files, MANIFEST_NAME: container.manifest_bytes}

def _project_inventory(parent, container):
    """Admit the actual native extraction record, never a copied marker."""
    content = _project_content(container)
    directories = _directories(content)
    with directory(parent, ('project',)) as project:
        project_info = os.fstat(project)
        with directory(project, PROJECT_COMPLETED) as receipt:
            receipt_info = os.fstat(receipt)
            limit = 4096 + sum(1024 + 2 * len(p.encode('utf-8')) for p in set(content) | directories)
            raw, _ = _read(receipt, 'journal.json', limit)
        expected = {p: {'size': len(b), 'sha256': sha256(b).hexdigest()} for p, b in content.items()}
        native, _ = checked_inventory(raw, root_identity=identity(project_info),
            stage_identity=identity(receipt_info), inventory=expected)
        content[PROJECT_RECORD] = raw
        directories.add('/'.join(PROJECT_COMPLETED))
        captured = {}
        for path in sorted(set(content) | directories):
            parts = path.split('/')
            with directory(project, parts[:-1]) as fd:
                if path in directories:
                    with directory(fd, (parts[-1],)) as child:
                        value = metadata(os.fstat(child))
                else:
                    observed, value = _read(fd, parts[-1], len(content[path]))
                    _require(observed == content[path])
            if path in native:
                _require(value == native[path])
            captured['project/' + path] = value
        captured['project'] = metadata(project_info)
    return content, directories, captured

def _restore(tree, content):
    with directory(tree.held.root_fd, (STAGING,)) as fd:
        tree.fd = os.dup(fd)
    tree.stage_identity = identity(os.fstat(tree.fd))
    # The expected input, not a stored length, bounds the control record.
    project = tree.opening.container.project
    names = set(content) | {'project/' + p for p in _project_content(project)}
    limit = 16384 + sum(4096 + 8 * len(p.encode('utf-8')) for p in names)
    raw, journal_metadata = _read(tree.fd, 'journal.json', limit)
    value = parse_json_object(raw)
    _require(set(value) == {'format', 'state', 'root_identity', 'root_created', 'stage_identity',
        'units', 'reused_directories', 'entries', 'source_sha256'} and canonical_json_bytes(value) == raw)
    _require(value['format'] == FORMAT and value['state'] == 'prepared'
        and value['root_identity'] == identity(os.fstat(tree.held.root_fd))
        and value['stage_identity'] == tree.stage_identity
        and value['source_sha256'] == tree.opening.source.sha256
        and type(value['root_created']) is bool and value['reused_directories'] == {})
    staged = info_at(tree.fd, 'project') is not None
    published = info_at(tree.held.root_fd, 'project') is not None
    _require(staged != published)
    project_content, project_dirs, _ = _project_inventory(
        tree.fd if staged else tree.held.root_fd, project)
    expected = {**content, **{'project/' + p: b for p, b in project_content.items()}}
    directories = _directories(content) | {'project'} | {'project/' + p for p in project_dirs}
    entries = value['entries']
    _require(type(entries) is dict and set(entries) == set(expected) | directories)
    tokens = {_identity(value['root_identity']), _identity(value['stage_identity'])}
    _require(len(tokens) == 2)
    for path, item in entries.items():
        token = _metadata(item, 'directory' if path in directories else 'file')
        _require(token not in tokens)
        tokens.add(token)
        if path in expected:
            _require(item['size'] == len(expected[path]) and item['sha256'] == sha256(expected[path]).hexdigest())
    units = sorted(p for p in entries if '/' not in p)
    units.remove('project'); units.append('project')
    _require(value['units'] == units and _identity(journal_metadata['identity']) not in tokens)
    tree.inventory, tree.units = entries, units
    tree.inventory['journal.json'] = journal_metadata
    tree.checked_locations()
