"""An explicit inline SARIF 2.1.0 slice; URIs and extensions stay passive data.

Only mapped result occurrences and explicitly selected driver rules,
invocations and artifacts contribute. A companion Exchange declares native
bindings; it cannot turn a SARIF failure or an arbitrary severity into a pass.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..model._field_shapes import _array, _object
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..storage.json_syntax import parse_json_object
from .evidence_exchange import (EvidenceExchange, EvidenceImportError, _read_json,
    _unique, _validate, _encode_candidates, evidence_exchange_schema, map_generic_candidates)
from ._sarif_validation import validate_selected
from ._import_candidates import (
    CandidateValue as _CandidateValue, candidate_value as _candidate_value,
    measurement as _measurement)


@dataclass(frozen=True, init=False)
class SarifDocument:
    source_bytes: bytes
    _encoded: bytes

    def __init__(self, raw):
        value = _read_json(raw)
        if value.get('version') != '2.1.0' or type(value.get('runs')) is not list:
            raise EvidenceImportError('unsupported_sarif_document')
        for number, run in enumerate(value['runs']):
            pointer = '/runs/' + str(number)
            if type(run) is not dict or type(run.get('tool')) is not dict:
                raise EvidenceImportError('invalid_sarif_run', pointer=pointer)
            driver = run['tool'].get('driver')
            if (type(driver) is not dict or type(driver.get('name')) is not str
                    or not driver['name']):
                raise EvidenceImportError('invalid_sarif_driver', pointer=pointer + '/tool/driver')
            for parent, name, path in (
                (run, 'results', pointer), (run, 'invocations', pointer),
                (run, 'artifacts', pointer), (driver, 'rules', pointer + '/tool/driver')):
                if name in parent and (type(parent[name]) is not list
                                       or any(type(v) is not dict for v in parent[name])):
                    raise EvidenceImportError('invalid_sarif_array', pointer=path + '/' + name)
        object.__setattr__(self, 'source_bytes', raw)
        object.__setattr__(self, '_encoded', canonical_json_bytes(value))

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self.source_bytes).hexdigest()

    def __bool__(self):
        raise TypeError('A SARIF report is not successful verification')


@dataclass(frozen=True, init=False)
class SarifMapping:
    """Exact report hash, explicit index selectors, and a declared Exchange."""
    source_bytes: bytes
    _encoded: bytes

    def __init__(self, raw):
        value = _read_json(raw)
        exchange_schema = evidence_exchange_schema()
        index = {'type': 'integer', 'minimum': 0}
        nullable_index = {'anyOf': [{'type': 'null'}, index]}
        schema = {**_object({
            'format_version': {'const': 'sarif-mapping-v1'},
            'source_sha256': {'$ref': '#/$defs/hash'},
            'exchange': {k: v for k, v in exchange_schema.items() if k != '$defs'},
            'bindings': _array(_object({
                'exchange_result_index': index, 'run_index': index, 'result_index': index,
                'rule_index': nullable_index, 'invocation_index': nullable_index,
                'artifact_indices': _array(index)}))}), '$defs': exchange_schema['$defs']}
        _validate(value, schema)
        try:
            exchange = EvidenceExchange(canonical_json_bytes(value['exchange'])).data
        except EvidenceImportError as error:
            raise EvidenceImportError(error.reason, pointer='/exchange' + error.pointer) from error
        for number, row in enumerate(value['bindings']):
            indices = [row[k] for k in ('exchange_result_index', 'run_index', 'result_index',
                                        'rule_index', 'invocation_index')]
            if any(v is not None and type(v) is not int for v in indices + row['artifact_indices']):
                raise EvidenceImportError('integer_sarif_index_required', pointer=f'/bindings/{number}')
            _unique(row['artifact_indices'], f'/bindings/{number}/artifact_indices')
        _unique([(b['run_index'], b['result_index']) for b in value['bindings']], '/bindings')
        positions = [b['exchange_result_index'] for b in value['bindings']]
        _unique(positions, '/bindings')
        if set(positions) != set(range(len(exchange['results']))):
            raise EvidenceImportError('sarif_exchange_mapping_incomplete', pointer='/bindings')
        object.__setattr__(self, 'source_bytes', raw)
        object.__setattr__(self, '_encoded', canonical_json_bytes(value))

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('A SARIF mapping is not evidence of execution')


@dataclass(frozen=True, init=False)
class SarifCandidates(_CandidateValue):
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use map_sarif_candidates with owned inputs')

    def __bool__(self):
        raise TypeError('SARIF candidates are not successful verification or write authority')


def _select(values, index, pointer):
    if index >= len(values):
        raise EvidenceImportError('sarif_index_out_of_range', pointer=pointer)
    value = values[index]
    return {'pointer': pointer + '/' + str(index), 'sha256': canonical_json_sha256(value),
            'value': value}


def map_sarif_candidates(document, mapping, *, targets):
    """Read selected inline driver data; never infer SpecRoad IDs or fetch files.

    v1 requires explicit reported kind=pass for a declared passed result,
    kind=fail (the SARIF default) for failed, and notApplicable for skipped.
    Other combinations are unsupported, not silently converted to success.
    Unselected occurrences are listed, awaiting the later explicit import policy.
    """
    if type(document) is not SarifDocument or type(mapping) is not SarifMapping:
        raise EvidenceImportError('typed_sarif_inputs_required')
    document, mapping = SarifDocument(document.source_bytes), SarifMapping(mapping.source_bytes)
    # Validate index types in the owned source, before canonical JSON can
    # collapse a fractional token such as 0.0 to the integer representation 0.
    settings, parsed = mapping.data, _read_json(document.source_bytes)
    if settings['source_sha256'] != document.sha256:
        raise EvidenceImportError('sarif_source_binding_mismatch', pointer='/source_sha256')
    try:
        generic = map_generic_candidates(
            EvidenceExchange(canonical_json_bytes(settings['exchange'])), targets=targets).data
    except EvidenceImportError as error:
        prefix = '' if error.pointer.startswith('/targets') else '/exchange'
        raise EvidenceImportError(error.reason, pointer=prefix + error.pointer) from error
    candidates, mapped = [], set()
    for row in settings['bindings']:
        run_pointer = '/runs/' + str(row['run_index'])
        if row['run_index'] >= len(parsed['runs']):
            raise EvidenceImportError('sarif_index_out_of_range', pointer='/runs')
        # A run may contain many large result occurrences. Hash only selected
        # objects, not the entire run again for every mapped occurrence.
        run = parsed['runs'][row['run_index']]
        if ('externalPropertyFileReferences' in run
                and type(run['externalPropertyFileReferences']) is not dict):
            raise EvidenceImportError('invalid_sarif_external_properties',
                                      pointer=run_pointer + '/externalPropertyFileReferences')
        if run.get('externalPropertyFileReferences'):
            raise EvidenceImportError('external_sarif_properties_unsupported', pointer=run_pointer)
        result = _select(run.get('results', []), row['result_index'], run_pointer + '/results')
        value = result['value']
        if (type(value.get('message')) is not dict
                or not any(type(value['message'].get(k)) is str and value['message'][k]
                           for k in ('text', 'markdown', 'id'))):
            raise EvidenceImportError('invalid_sarif_message', pointer=result['pointer'] + '/message')
        if 'rule' in value:  # Extensions/component-qualified selectors need a later explicit profile.
            raise EvidenceImportError('sarif_rule_reference_unsupported', pointer=result['pointer'] + '/rule')
        kind, level = value.get('kind', 'fail'), value.get('level')
        candidate = generic['candidates'][row['exchange_result_index']]
        expected = {'pass': 'passed', 'fail': 'failed', 'notApplicable': 'skipped'}
        if type(kind) is not str or kind not in expected or candidate['result'] != expected[kind]:
            raise EvidenceImportError('unsupported_sarif_outcome_mapping', pointer=result['pointer'])
        if ('level' in value and (type(level) is not str
                or level not in ('none', 'note', 'warning', 'error')
                or (kind != 'fail' and level != 'none'))):
            raise EvidenceImportError('invalid_sarif_result_level', pointer=result['pointer'] + '/level')
        rule, invocation = None, None
        if row['rule_index'] is not None:
            rule = _select(run['tool']['driver'].get('rules', []), row['rule_index'],
                           run_pointer + '/tool/driver/rules')
            rule_id = rule['value'].get('id')
            if type(rule_id) is not str or not rule_id:
                raise EvidenceImportError('invalid_sarif_rule_id', pointer=rule['pointer'])
            if (('ruleIndex' in value and (type(value['ruleIndex']) is not int
                    or value['ruleIndex'] != row['rule_index']))
                    or ('ruleId' in value and value['ruleId'] != rule_id)):
                raise EvidenceImportError('sarif_rule_binding_mismatch', pointer=result['pointer'])
        if row['invocation_index'] is not None:
            invocation = _select(run.get('invocations', []), row['invocation_index'],
                                 run_pointer + '/invocations')
            success = invocation['value'].get('executionSuccessful')
            if type(success) is not bool:
                raise EvidenceImportError('invalid_sarif_invocation', pointer=invocation['pointer'])
            if candidate['result'] == 'passed' and not success:
                raise EvidenceImportError('sarif_failed_invocation_cannot_pass', pointer=invocation['pointer'])
        artifacts = [_select(run.get('artifacts', []), index, run_pointer + '/artifacts')
                     for index in row['artifact_indices']]
        validate_selected(run, row, result, candidate, rule, artifacts)
        candidates.append(_measurement(**{**candidate, 'origin': 'imported_sarif'},
            sarif={'run_index': row['run_index'], 'result': result, 'rule': rule,
                   'invocation': invocation, 'artifacts': artifacts,
                   'driver': {k: v for k, v in run['tool']['driver'].items()
                              if k in ('name', 'version', 'semanticVersion')},
                   'kind': kind}))
        mapped.add((row['run_index'], row['result_index']))
    data = {**{k: v for k, v in generic.items()
               if k not in ('source', 'exchange_sha256', 'parser_profile', 'format_version', 'candidates')},
        'format_version': 'sarif-evidence-candidates-v1', 'parser_profile': 'sarif-inline-2.1.0-v1',
        'source': {'sha256': document.sha256, 'size': len(document.source_bytes)},
        'mapping_sha256': mapping.sha256,
        'mapping_source_sha256': sha256(mapping.source_bytes).hexdigest(),
        'exchange_sha256': generic['exchange_sha256'], 'candidates': candidates,
        'unmapped_results': [f'/runs/{r}/results/{i}' for r, run in enumerate(parsed['runs'])
                             for i in range(len(run.get('results', []))) if (r, i) not in mapped],
        'import_policy_applied': False}
    return _candidate_value(SarifCandidates, data, encoder=_encode_candidates)
