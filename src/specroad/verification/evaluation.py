"""Owned verification-evaluation-v1 descriptors and explicit input-byte binding.

This initial profile has no run replacements. It does not discover files, infer
a current build, resolve the required-check scope or aggregate Evidence results.
Input roles and completeness of the caller's chosen test inputs are not attested.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..configurations import EffectiveConfiguration
from ..model._field_shapes import _array, _object
from ..model._schema import validate_builtin
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.domain_fields import reference_schema
from ..model.errors import ModelError
from ..model.paths import project_path
from ..model.record_schemas import record_schema
from ..storage.json_syntax import parse_json_object
from ._evaluation_product import input_manifest, product_state_sha256, observe_input_bytes


class VerificationEvaluationError(ModelError):
    code = 'SRV175'
    exit_code = 3

    def diagnostic(self):
        return {**super().diagnostic(), 'code': self.code, 'exit_code': self.exit_code}


def verification_evaluation_schema():
    """Closed initial descriptor profile; replacements are explicitly unsupported."""
    ref = lambda name: {'$ref': '#/$defs/' + name}
    key = {'subject_artifact_id': ref('artifact_ref'),
        'contract_id': {'anyOf': [reference_schema(p) for p in ('VER', 'TEST')]},
        'test_id': ref('test_ref'), 'check_id': ref('check_id')}
    fields = {
        'format_version': {'const': '1.0.0'},
        'evaluation_id': {'type': 'string',
            'pattern': r'^EVAL-[0-7][0-9A-HJKMNP-TV-Z]{25}(?![\s\S])'},
        'evaluated_subject': _object({'subject_id': ref('text'),
            'manifest': _array(_object({'logical_path': ref('text'),
                'size': {'type': 'integer', 'minimum': 0}, 'sha256': ref('hash')}), nonempty=True),
            'state_sha256': ref('hash')}),
        'configuration_hash': {'anyOf': [{'type': 'null'}, ref('hash')]},
        'required_runs': _array(_object({**key, 'run_ids': _array(ref('text'), nonempty=True)}),
                                nonempty=True),
        'replacements': {'const': []},
        'created_at': ref('utc'), 'created_by': ref('actor')}
    return {**_object(fields), '$id': 'verification-evaluation-v1',
            '$defs': record_schema('evidence')['$defs']}


def _path(value, pointer):
    try:
        if project_path(value) != value:
            raise ModelError('noncanonical_evaluation_input_path')
    except ModelError as error:
        raise VerificationEvaluationError(error.reason, pointer=pointer) from error


def _key(row):
    return tuple((row[field] or '').encode('utf-8')
        for field in ('subject_artifact_id', 'contract_id', 'test_id', 'check_id'))


def _read(raw):
    try:
        value = parse_json_object(raw)
        validate_builtin(value, verification_evaluation_schema())
        subject = value['evaluated_subject']
        paths = set()
        for index, entry in enumerate(subject['manifest']):
            pointer = f'/evaluated_subject/manifest/{index}/logical_path'
            _path(entry['logical_path'], pointer)
            if entry['logical_path'] in paths:
                raise VerificationEvaluationError('duplicate_evaluation_input_path', pointer=pointer)
            paths.add(entry['logical_path'])
            entry['size'] = int(entry['size'])
        subject['manifest'].sort(key=lambda item: item['logical_path'].encode('utf-8'))
        if product_state_sha256(subject) != subject['state_sha256']:
            raise VerificationEvaluationError('evaluation_state_hash_mismatch',
                                              pointer='/evaluated_subject/state_sha256')
        keys = set()
        for index, row in enumerate(value['required_runs']):
            pointer = '/required_runs/' + str(index)
            key = _key(row)
            if key in keys:
                raise VerificationEvaluationError('duplicate_evaluation_required_key', pointer=pointer)
            keys.add(key)
            if len(set(row['run_ids'])) != len(row['run_ids']):
                raise VerificationEvaluationError('duplicate_evaluation_run_id', pointer=pointer + '/run_ids')
            for run_id in row['run_ids']:
                namespace, separator, local = run_id.partition(':')
                if (not separator or not namespace.strip() or not local.strip()
                        or run_id != run_id.strip()):
                    raise VerificationEvaluationError('namespaced_evaluation_run_id_required',
                                                      pointer=pointer + '/run_ids')
            row['run_ids'].sort(key=lambda run: run.encode('utf-8'))
        value['required_runs'].sort(key=_key)
        return value
    except VerificationEvaluationError:
        raise
    except ModelError as error:
        raise VerificationEvaluationError(error.reason, pointer=error.pointer) from error


@dataclass(frozen=True, init=False)
class VerificationEvaluation:
    """A normalized descriptor is an input declaration, not verification success."""
    source_bytes: bytes
    _encoded: bytes

    def __init__(self, raw):
        if type(raw) is not bytes:
            raise VerificationEvaluationError('evaluation_bytes_required')
        value = _read(raw)
        object.__setattr__(self, 'source_bytes', raw)
        object.__setattr__(self, '_encoded', canonical_json_bytes(value))

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def canonical_bytes(self):
        return self._encoded

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    @property
    def state_sha256(self):
        return self.data['evaluated_subject']['state_sha256']

    def __bool__(self):
        raise TypeError('An evaluation descriptor is not verification success or approval')


def _inputs(inputs):
    if type(inputs) is not dict:
        raise VerificationEvaluationError('explicit_evaluation_input_bytes_required')
    owned = dict(inputs)
    for index, (path, raw) in enumerate(owned.items()):
        _path(path, f'/inputs/{index}/logical_path')
        if type(raw) is not bytes:
            raise VerificationEvaluationError('evaluation_input_bytes_required', pointer=f'/inputs/{index}')
    return owned


def prepare_verification_evaluation(*, evaluation_id, subject_id, inputs,
        configuration, required_runs, created_at, created_by):
    """Build a descriptor from supplied input bytes, explicit identity and audit.

    No filesystem paths are opened and no identity, clock, configuration or Git
    state is discovered. The caller identifies the actual inputs of the check;
    output/Evidence/descriptor roles and independent scope coverage remain open.
    """
    owned = _inputs(inputs)
    if configuration is not None and type(configuration) is not EffectiveConfiguration:
        raise VerificationEvaluationError('typed_evaluation_configuration_required')
    manifest = input_manifest(owned)
    subject = {'subject_id': subject_id, 'manifest': manifest}
    try:
        value = {'format_version': '1.0.0', 'evaluation_id': evaluation_id,
            'evaluated_subject': {**subject, 'state_sha256': product_state_sha256(subject)},
            'configuration_hash': None if configuration is None else configuration.sha256,
            'required_runs': required_runs, 'replacements': [],
            'created_at': created_at, 'created_by': created_by}
        return VerificationEvaluation(canonical_json_bytes(value))
    except VerificationEvaluationError:
        raise
    except ModelError as error:
        raise VerificationEvaluationError(error.reason, pointer=error.pointer) from error


@dataclass(frozen=True, init=False)
class EvaluationInputAssessment:
    """Owned byte-comparison observation; it grants no scope or write authority."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use assess_evaluation_inputs')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Input-byte equality is not verification success or approval')


def assess_evaluation_inputs(evaluation, *, inputs):
    """Compare every declared input with explicitly supplied bytes, without I/O.

    Missing, mismatched and unexpected inputs are separate observations; none
    are replaced by a current model, guessed build or another file on disk.
    """
    if type(evaluation) is not VerificationEvaluation:
        raise VerificationEvaluationError('typed_verification_evaluation_required')
    evaluation = VerificationEvaluation(evaluation.source_bytes)
    owned = _inputs(inputs)
    data = evaluation.data
    subject = data['evaluated_subject']
    observation = observe_input_bytes(subject, owned)
    report = {'format_version': 'verification-evaluation-inputs-v1',
        'evaluation_id': data['evaluation_id'], 'evaluation_sha256': evaluation.sha256,
        'subject_id': subject['subject_id'], 'state_sha256': subject['state_sha256'],
        **observation,
        'input_roles_verified': False, 'project_required_checks_complete': False,
        'configuration_applicability_evaluated': False, 'run_selection_evaluated': False,
        'full_verification_evaluated': False, 'external_run_verified': False,
        'release_readiness_evaluated': False, 'test_code_executed': False,
        'write_authorized': False, 'approval_granted': False}
    result = object.__new__(EvaluationInputAssessment)
    object.__setattr__(result, '_encoded', canonical_json_bytes(report))
    return result


@dataclass(frozen=True, init=False)
class EvaluationBindingAssessment:
    """Pre-aggregation input gate, never a passed verification or permission."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use assess_evaluation_binding')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('An input binding is not verification success or approval')


def _input_roles(value):
    if value is None:
        return None
    if type(value) is not dict:
        raise VerificationEvaluationError('explicit_evaluation_input_roles_required')
    owned = dict(value)
    for index, (path, role) in enumerate(owned.items()):
        pointer = f'/input_roles/{index}'
        _path(path, pointer + '/logical_path')
        if type(role) is not str or role not in (
                'input', 'evidence', 'result', 'evaluation', 'selection_metadata'):
            raise VerificationEvaluationError('invalid_evaluation_input_role', pointer=pointer)
    return owned


def assess_evaluation_binding(evaluation, *, inputs, input_roles):
    """Check explicit byte and role bindings before independent scope resolution.

    The calling checker/importer declares roles in its logical namespace. Every
    declared input must occur in the manifest; excluded roles must never occur.
    A role inventory is a caller declaration, not inferred from extensions,
    filenames or JSON content, nor an authentication of external execution.
    None denotes unavailable descriptor/bytes/roles, never a current-build guess.
    """
    if evaluation is not None:
        if type(evaluation) is not VerificationEvaluation:
            raise VerificationEvaluationError('typed_verification_evaluation_required')
        evaluation = VerificationEvaluation(evaluation.source_bytes)
    owned = None if inputs is None else _inputs(inputs)
    roles = _input_roles(input_roles)
    role_rows = None if roles is None else [
        {'logical_path': path, 'role': role}
        for path, role in sorted(roles.items(), key=lambda pair: pair[0].encode('utf-8'))]
    data = None if evaluation is None else evaluation.data
    subject = None if data is None else data['evaluated_subject']
    reasons, missing_roles, unlisted = [], [], []
    observation = None
    roles_checked = False
    if evaluation is None:
        reasons.append('evaluation_required')
    else:
        paths = {entry['logical_path'] for entry in subject['manifest']}
        if roles is None:
            missing_roles = sorted(paths, key=lambda path: path.encode('utf-8'))
            reasons.append('evaluation_input_roles_required')
        else:
            for path in sorted(paths, key=lambda path: path.encode('utf-8')):
                if path not in roles:
                    missing_roles.append(path)
                elif roles[path] != 'input':
                    raise VerificationEvaluationError('forbidden_evaluation_input_role',
                        path=path, pointer='/evaluated_subject/manifest')
            unlisted = sorted({p for p, role in roles.items() if role == 'input'} - paths,
                              key=lambda path: path.encode('utf-8'))
            if missing_roles:
                reasons.append('evaluation_input_roles_missing')
            if unlisted:
                reasons.append('evaluation_inputs_not_listed')
            roles_checked = not (missing_roles or unlisted)
        if owned is None:
            reasons.append('evaluation_input_bytes_required')
        else:
            observation = assess_evaluation_inputs(evaluation, inputs=owned).data
            for field, reason in (
                    ('missing_inputs', 'evaluation_input_missing'),
                    ('mismatched_inputs', 'evaluation_input_changed'),
                    ('unexpected_inputs', 'evaluation_input_unexpected')):
                if observation[field]:
                    reasons.append(reason)
    report = {'format_version': 'verification-evaluation-binding-v1',
        'evaluation_id': None if data is None else data['evaluation_id'],
        'evaluation_sha256': None if evaluation is None else evaluation.sha256,
        'subject_id': None if subject is None else subject['subject_id'],
        'state_sha256': None if subject is None else subject['state_sha256'],
        'configuration_hash': None if data is None else data['configuration_hash'],
        'input_roles': role_rows,
        'input_roles_sha256': None if role_rows is None else canonical_json_sha256(role_rows),
        'missing_input_roles': missing_roles, 'unlisted_inputs': unlisted,
        'input_observation': observation,
        'input_bytes_verified': observation is not None and observation['input_bytes_verified'],
        'input_roles_checked': roles_checked, 'input_roles_authenticated': False,
        'binding_status': 'incomplete' if reasons else 'ready',
        'verification_result': 'incomplete' if reasons else None,
        'reasons': reasons,
        'diagnostics': [{'code': 'SRV176', 'severity': 'warning', 'reason': reason}
                        for reason in reasons],
        'project_required_checks_complete': False, 'configuration_applicability_evaluated': False,
        'run_selection_evaluated': False, 'full_verification_evaluated': False,
        'external_run_verified': False, 'release_readiness_evaluated': False,
        'test_code_executed': False, 'write_authorized': False, 'approval_granted': False}
    result = object.__new__(EvaluationBindingAssessment)
    object.__setattr__(result, '_encoded', canonical_json_bytes(report))
    return result
