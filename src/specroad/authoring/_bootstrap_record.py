"""Bootstrap-only journal and initial-value contracts; no existing-project plan.

These validators neither authorize deletion nor execute journal-controlled code.
Recovery owns the reads/publication; this module owns the closed value grammar
and the original configuration/document bindings.
"""
import os
import re
from uuid import UUID

from ..model.canonical import canonical_json_bytes
from ..model.configuration import ProjectConfiguration
from ..model.identities import artifact_identity
from ..storage.json_reader import parse_json_object
from ..storage.record_artifact import RecordArtifact
from ._bootstrap_io import BootstrapError, STAGING, identity
from ._initial_content import (ROOT_DIRECTORIES, initial_directories,
                              primary_document, project_configuration)

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
