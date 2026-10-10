"""Closed bootstrap replay: prove the entire state before publishing a prefix.

The journal is passive evidence, not a script or permission to delete anything.
Only the exact minimum project and the current distribution's pinned resources
can be resumed. An incomplete or changed record is retained for diagnosis.
"""
from hashlib import sha256
import os
import re
import stat
from uuid import UUID

from ..model.canonical import canonical_json_bytes
from ..model.configuration import ProjectConfiguration
from ..model.errors import ModelError
from ..model.identities import artifact_identity
from ..security import SafetyViolation
from ..security import paths as guards
from ..storage.json_reader import parse_json_object
from ..storage.record_artifact import RecordArtifact
from ._bootstrap_io import (BootstrapError, BootstrapTree, COMPLETED, STAGING,
    check_entry, directory, identity, info_at, metadata)
from ._initial_content import (ROOT_DIRECTORIES, distribution_content,
    initial_directories, primary_document, project_configuration)

JOURNAL_LIMIT = 262144
PROJECT_FILE_LIMIT = 65536


def _invalid():
    raise BootstrapError('bootstrap_journal_invalid', path=STAGING)


def _identity(value):
    if type(value) is not list or len(value) != 2 or any(type(i) is not int or i < 0 for i in value):
        _invalid()
    return tuple(value)


def _metadata(value, kind):
    fields = {'identity', 'mode', 'kind'}
    if kind == 'file': fields.update(('size', 'sha256'))
    if type(value) is not dict or set(value) != fields or value['kind'] != kind:
        _invalid()
    token = _identity(value['identity'])
    if type(value['mode']) is not int or not 0 <= value['mode'] <= 0o777:
        _invalid()
    if kind == 'file' and (value['mode'] & 0o111 or type(value['size']) is not int
            or value['size'] < 0 or type(value['sha256']) is not str
            or re.fullmatch('[0-9a-f]{64}', value['sha256']) is None):
        _invalid()
    return token


def _read(parent, name, limit, expected=None):
    """Bounded, no-link, single-inode read with fresh name and fd checks."""
    before = os.stat(name, dir_fd=parent, follow_symlinks=False)
    guards._regular(before, directory=False)
    if before.st_nlink != 1 or before.st_size > limit:
        _invalid()
    if expected is not None: check_entry(parent, name, expected)
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    try:
        signature = guards._signature(before)
        if guards._signature(os.fstat(fd)) != signature: _invalid()
        raw = bytearray()
        while len(raw) <= limit:
            block = os.read(fd, min(65536, limit + 1 - len(raw)))
            if not block: break
            raw.extend(block)
        if len(raw) != before.st_size or guards._signature(os.fstat(fd)) != signature:
            _invalid()
        after = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if guards._signature(after) != signature: _invalid()
    finally:
        os.close(fd)
    raw = bytes(raw)
    if expected is not None and sha256(raw).hexdigest() != expected['sha256']: _invalid()
    return raw, metadata(before, raw)


def _record(tree, raw, resources):
    value = parse_json_object(raw)
    fields = {'format', 'state', 'root_identity', 'root_created', 'stage_identity',
              'units', 'reused_directories', 'entries'}
    if set(value) != fields or canonical_json_bytes(value) != raw:
        _invalid()
    if value['format'] != 'specroad-bootstrap-v1' or value['state'] != 'prepared':
        _invalid()
    if type(value['root_created']) is not bool: _invalid()
    tokens = {_identity(value['root_identity']), _identity(value['stage_identity'])}
    if len(tokens) != 2 or value['root_identity'] != identity(os.fstat(tree.held.root_fd)):
        _invalid()
    if value['stage_identity'] != tree.stage_identity: _invalid()
    reused = value['reused_directories']
    if type(reused) is not dict or set(reused) - set(ROOT_DIRECTORIES): _invalid()
    if value['root_created'] and reused: _invalid()
    entries = value['entries']
    if type(entries) is not dict: _invalid()
    directories = initial_directories()
    files = set(entries) - directories
    documents = files - set(resources) - {'specroad.json'}
    if len(documents) != 1: _invalid()
    document, = documents
    if re.fullmatch(r'spec/documents/SR-DOC-[0-7][0-9A-HJKMNP-TV-Z]{25}\.json', document) is None:
        _invalid()
    if set(entries) != directories | set(resources) | {'specroad.json', document}: _invalid()
    for path, item in tuple(entries.items()) + tuple(reused.items()):
        token = _metadata(item, 'directory' if path in directories else 'file')
        if token in tokens: _invalid()
        tokens.add(token)
    units = sorted(p for p in entries if ('/' not in p and p not in reused) or
        (p.count('/') == 1 and p.split('/')[0] in reused))
    units.remove('specroad.json'); units.append('specroad.json')
    if value['units'] != units: _invalid()
    # Do not trust an attacker-selected size for any project file.
    for path in files:
        limit = len(resources[path]) if path in resources else PROJECT_FILE_LIMIT
        if entries[path]['size'] > limit: _invalid()
    tree.inventory = entries
    tree.reused = reused
    tree.units = units
    return document


def _content(tree, locations, resources):
    content = {}
    for path, expected in sorted(tree.inventory.items()):
        if expected['kind'] != 'file' or path == 'journal.json': continue
        unit = next(unit for unit in tree.units if path == unit or path.startswith(unit + '/'))
        source = tree.held.root_fd if locations[unit] else tree.fd
        parts = path.split('/')
        with directory(source, parts[:-1]) as parent:
            content[path], _ = _read(parent, parts[-1], expected['size'], expected)
        if path in resources and content[path] != resources[path]: _invalid()
    return content


def _validated_values(content, document, name, registry, packages):
    configuration = ProjectConfiguration(parse_json_object(content['specroad.json']))
    project_id = UUID(configuration.project_id)
    if project_id.version != 4 or str(project_id) != configuration.project_id: _invalid()
    expected = project_configuration(name, configuration.project_id, registry, packages)
    if content['specroad.json'] != canonical_json_bytes(expected.data): _invalid()
    record = RecordArtifact(content[document], expected_type='document', path=document)
    token = artifact_identity(record.data)
    if token.id_scheme != 'random128-v1' or document != 'spec/documents/' + record.id + '.json':
        _invalid()
    expected = primary_document(name, token, record.data['created_at'])
    if content[document] != canonical_json_bytes(expected): _invalid()
    return configuration, record.id


def _receipt_present(held):
    # A missing/non-directory ordinary target will be diagnosed by fresh init's
    # preflight; do not follow it while searching for an optional receipt.
    parent = held.root_fd
    with directory(parent) as root:
        info = info_at(root, COMPLETED[0])
        if info is None or not stat.S_ISDIR(info.st_mode): return False
        with directory(root, COMPLETED[:1]) as operational:
            info = info_at(operational, COMPLETED[1])
            if info is None or not stat.S_ISDIR(info.st_mode): return False
            with directory(operational, COMPLETED[1:2]) as recovery:
                return info_at(recovery, COMPLETED[-1]) is not None


def recover_bootstrap(held, function, name):
    """Return the original successful payload values, or None for a fresh root.

    Failed replays retain their actual state. Only a fresh in-memory attempt
    may use its own rollback inventory; stored records never authorize deletion.
    """
    held.require_held()
    staged = info_at(held.root_fd, STAGING) is not None
    receipt = _receipt_present(held)
    if not staged and not receipt: return None
    if staged and receipt: raise BootstrapError('bootstrap_multiple_records')
    tree = BootstrapTree(held, function, {})
    tree.stage_parts = COMPLETED if receipt else (STAGING,)
    publishing = False
    try:
        with directory(held.root_fd, tree.stage_parts) as fd:
            tree.fd = os.dup(fd)
            tree.stage_identity = identity(os.fstat(fd))
        tree.check()
        if info_at(tree.fd, 'journal.json') is None: _invalid()
        raw, journal_metadata = _read(tree.fd, 'journal.json', JOURNAL_LIMIT)
        registry, profiles, packages, resources = distribution_content()
        document = _record(tree, raw, resources)
        if journal_metadata['identity'] in [v['identity'] for v in tree.inventory.values()]:
            _invalid()
        tree.inventory['journal.json'] = journal_metadata
        locations = tree.checked_locations()
        if receipt and not all(locations.values()): _invalid()
        content = _content(tree, locations, resources)
        configuration, document_id = _validated_values(content, document, name, registry, packages)
        tree.checked_locations()
        publishing = True
        tree.publish()
        tree.retain_completed()
        return content, initial_directories(), configuration, document_id
    except SafetyViolation:
        raise
    except (ModelError, ValueError, TypeError, KeyError, RecursionError) as error:
        raise BootstrapError('bootstrap_journal_invalid', path=STAGING) from error
    except FileNotFoundError as error:
        raise BootstrapError('bootstrap_inventory_changed', path=STAGING,
                             mutation_possible=publishing) from error
    except OSError as error:
        raise BootstrapError('bootstrap_recovery_io', exit_code=5, path=STAGING,
                             mutation_possible=publishing) from error
    finally:
        tree.close()
