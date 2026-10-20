"""Versioned, passive Evidence Exchange inputs and explicitly bound candidates.

The source declares a producer, product run and measurements. Local subject
hashes are checked against supplied native values; this does not authenticate
the producer, execute a test, select an authoritative run or publish Evidence.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..model._field_shapes import _array, _object
from ..model._schema import validate_builtin
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.domain_fields import reference_schema
from ..model.errors import ModelError
from ..model.paths import project_path
from ..model.record_schemas import record_schema
from ..storage.domain_artifact import DomainArtifact
from ..storage.json_syntax import parse_json_object
from ._context_subject import owned_subject
from ._subject_binding import subject_binding
from .contracts import VerificationContract, VerificationTest


class EvidenceImportError(ModelError):
    code = 'SRV091'
    exit_code = 3

    def diagnostic(self):
        return {**super().diagnostic(), 'code': self.code, 'exit_code': self.exit_code}


def _read_json(raw):
    """Fixed passive input budget, applied before schema or canonical traversal."""
    if type(raw) is not bytes:
        raise EvidenceImportError('evidence_import_bytes_required')
    if len(raw) > 4 * 1024 * 1024:
        raise EvidenceImportError('evidence_import_byte_limit')
    try:
        value = parse_json_object(raw)
    except ModelError as error:
        raise EvidenceImportError(error.reason, pointer=error.pointer) from error
    stack, count = [(value, 0)], 0
    while stack:
        item, depth = stack.pop()
        count += 1
        if depth > 64 or count > 100000:
            raise EvidenceImportError('evidence_import_structure_limit')
        if type(item) in (list, dict):
            if len(item) > 10000:
                raise EvidenceImportError('evidence_import_item_limit')
            stack.extend((v, depth + 1) for v in
                         (item.values() if type(item) is dict else item))
    return value


def evidence_exchange_schema():
    """Return the detached, closed v1 schema; external schemas are never loaded."""
    ref = lambda name: {'$ref': '#/$defs/' + name}
    target = {'anyOf': [reference_schema(prefix) for prefix in ('REQ', 'TEST', 'VER')]}
    fields = {
        'format_version': {'const': 'specroad-evidence-exchange-v1'},
        'producer': ref('producer'), 'tool': ref('tool'),
        'run': _object({'subject_id': ref('text'), 'subject_state_sha256': ref('hash'),
                        'run_id': ref('text')}),
        'subjects': _array(ref('evidence_subject'), nonempty=True),
        'results': _array(_object({
            'target_id': target, 'check_id': ref('check_id'), 'test_id': ref('test_ref'),
            'result': ref('text'), 'produced_at': ref('utc'),
            'subject_ids': _array(target, nonempty=True),
            'attachment_paths': _array(ref('text'))})),
        'environment': {'type': 'object'},
        'attachments': _array(ref('attachment')),
        'configuration_hash': {'anyOf': [{'type': 'null'}, ref('hash')]},
        'configuration_policy': {'enum': ['bound', 'independent']}}
    return {**_object(fields), '$defs': record_schema('evidence')['$defs']}


def _validate(value, schema):
    try:
        validate_builtin(value, schema)
    except ModelError as error:
        raise EvidenceImportError(error.reason, pointer=error.pointer) from error


def _unique(values, pointer):
    if len(values) != len(set(values)):
        raise EvidenceImportError('duplicate_evidence_import_binding', pointer=pointer)


def _encode_candidates(value):
    """Bound expanded output, counting shared metadata at every occurrence."""
    stack, count, text_size = [value], 0, 0
    while stack:
        item = stack.pop()
        count += 1
        if type(item) is dict:
            stack.extend(item.keys())
            stack.extend(item.values())
        elif type(item) is list:
            stack.extend(item)
        elif type(item) is str:
            text_size += len(item.encode('utf-8'))
        if count > 100000 or text_size > 16 * 1024 * 1024:
            raise EvidenceImportError('evidence_import_candidate_limit')
    encoded = canonical_json_bytes(value)
    if len(encoded) > 16 * 1024 * 1024:
        raise EvidenceImportError('evidence_import_candidate_limit')
    return encoded


def _read_exchange(raw):
    value = _read_json(raw)
    _validate(value, evidence_exchange_schema())
    run_id = value['run']['run_id']
    namespace, separator, local_id = run_id.partition(':')
    if (not separator or not namespace.strip() or not local_id.strip()
            or run_id != run_id.strip()):
        raise EvidenceImportError('namespaced_import_run_id_required', pointer='/run/run_id')
    if value['configuration_policy'] == 'bound' and value['configuration_hash'] is None:
        raise EvidenceImportError('bound_import_configuration_hash_required',
                                  pointer='/configuration_hash')
    subjects = [s['artifact_id'] for s in value['subjects']]
    paths = [a['path'] for a in value['attachments']]
    _unique(subjects, '/subjects')
    _unique(paths, '/attachments')
    for number, path in enumerate(paths):
        try:
            if project_path(path) != path:
                raise ModelError('noncanonical_import_attachment_path')
        except ModelError as error:
            raise EvidenceImportError(error.reason,
                                      pointer=f'/attachments/{number}/path') from error
    subject_ids, attachment_paths = set(subjects), set(paths)
    for number, result in enumerate(value['results']):
        pointer = '/results/' + str(number)
        _unique(result['subject_ids'], pointer + '/subject_ids')
        _unique(result['attachment_paths'], pointer + '/attachment_paths')
        if not set(result['subject_ids']) <= subject_ids:
            raise EvidenceImportError('unknown_import_subject', pointer=pointer + '/subject_ids')
        if not set(result['attachment_paths']) <= attachment_paths:
            raise EvidenceImportError('unknown_import_attachment', pointer=pointer + '/attachment_paths')
    return value


@dataclass(frozen=True, init=False)
class EvidenceExchange:
    """Owned v1 bytes; all producer and run information remains self-reported."""
    source_bytes: bytes
    _encoded: bytes

    def __init__(self, raw):
        value = _read_exchange(raw)
        object.__setattr__(self, 'source_bytes', raw)
        object.__setattr__(self, '_encoded', canonical_json_bytes(value))

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self.source_bytes).hexdigest()

    def __bool__(self):
        raise TypeError('Exchange data is not verified or recorded Evidence')


@dataclass(frozen=True, init=False)
class ExchangeCandidates:
    """Detached measurements, with local binding but no publication authority."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use map_generic_candidates with owned inputs')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Import candidates are not successful verification or write authority')


def _targets(targets):
    if type(targets) not in (list, tuple):
        raise EvidenceImportError('typed_import_targets_required', pointer='/targets')
    if len(targets) > 10000:
        raise EvidenceImportError('evidence_import_target_limit', pointer='/targets')
    bindings, subjects = {}, {}
    total_bytes = 0
    for number, target in enumerate(targets):
        if type(target) not in (DomainArtifact, VerificationContract, VerificationTest):
            raise EvidenceImportError('typed_verification_subject_required',
                                      pointer=f'/targets/{number}')
        if type(target.source_bytes) is bytes:
            total_bytes += len(target.source_bytes)
            if total_bytes > 16 * 1024 * 1024:
                raise EvidenceImportError('evidence_import_target_limit', pointer=f'/targets/{number}')
        try:
            owned = owned_subject(target)
        except ModelError as error:
            raise EvidenceImportError(error.reason, pointer=f'/targets/{number}') from error
        value = owned.data
        if value['id'] in bindings:
            raise EvidenceImportError('duplicate_import_target', pointer=f'/targets/{number}')
        bindings[value['id']] = {
            'artifact_id': value['id'], 'artifact_type': value['artifact_type'],
            'revision': value['revision'], 'source_sha256': sha256(owned.source_bytes).hexdigest(),
            'record_sha256': canonical_json_sha256(value)}
        subjects[value['id']] = subject_binding(value)
    return bindings, subjects


def map_generic_candidates(exchange, *, targets):
    """Match declared subjects exactly to supplied native REQ/TEST/VER snapshots.

    Run, configuration and attachment declarations remain unverified. They are
    never inferred from the host, Git, a clock, target fields or file locations.
    A result's check/test IDs are retained for later contract-slot validation.
    """
    if type(exchange) is not EvidenceExchange:
        raise EvidenceImportError('typed_evidence_exchange_required')
    exchange = EvidenceExchange(exchange.source_bytes)
    value = exchange.data
    bindings, native_subjects = _targets(targets)
    for number, subject in enumerate(value['subjects']):
        if native_subjects.get(subject['artifact_id']) != subject:
            raise EvidenceImportError('import_subject_binding_mismatch',
                                      pointer=f'/subjects/{number}')
    subjects = {s['artifact_id']: s for s in value['subjects']}
    attachments = {a['path']: a for a in value['attachments']}
    candidates = []
    for number, result in enumerate(value['results']):
        pointer = '/results/' + str(number)
        if result['target_id'] not in bindings:
            raise EvidenceImportError('import_target_not_found', pointer=pointer + '/target_id')
        if result['test_id'] is not None and result['test_id'] not in bindings:
            raise EvidenceImportError('import_test_not_found', pointer=pointer + '/test_id')
        candidates.append({
            'result_index': number, 'target': bindings[result['target_id']],
            'result': result['result'], 'produced_at': result['produced_at'],
            'producer': value['producer'], 'tool': value['tool'],
            'run_context': {**value['run'], 'check_id': result['check_id'],
                            'test_id': result['test_id']},
            'subjects': [subjects[s] for s in result['subject_ids']],
            'environment': value['environment'],
            'attachments': [attachments[p] for p in result['attachment_paths']],
            'configuration_hash': value['configuration_hash'],
            'configuration_policy': value['configuration_policy'],
            'origin': 'imported_generic'})
    data = {
        'format_version': 'generic-evidence-candidates-v1',
        'source': {'sha256': exchange.sha256, 'size': len(exchange.source_bytes)},
        'exchange_sha256': canonical_json_sha256(value),
        'parser_profile': value['format_version'], 'candidates': candidates,
        'candidate_count': len(candidates), 'supplied_subjects_bound': True,
        'external_run_verified': False, 'project_targets_verified': False,
        'configuration_verified': False, 'attachments_verified': False,
        'contract_slots_verified': False, 'test_code_executed': False,
        'evidence_created': False, 'full_verification_evaluated': False,
        'write_authorized': False, 'approval_granted': False}
    result = object.__new__(ExchangeCandidates)
    object.__setattr__(result, '_encoded', _encode_candidates(data))
    return result
