"""Checks for selected inline SARIF data, without resolving or importing URIs."""
from ..model._schema import validate_builtin
from ..model.errors import ModelError
from .evidence_exchange import EvidenceImportError


def _object(properties, required=()):
    # SARIF extensions remain opaque data. Only this profile's named fields
    # have semantics; unknown properties never acquire native authority.
    return {'type': 'object', 'properties': properties, 'required': list(required)}


_STRING = {'type': 'string'}
_TEXT = {'type': 'string', 'minLength': 1}
_INDEX = {'type': 'integer', 'minimum': -1}
_MESSAGE = _object({'text': _STRING, 'markdown': _STRING, 'id': _TEXT,
                    'arguments': {'type': 'array', 'items': _STRING},
                    'properties': {'type': 'object'}})
_LOCATION = _object({'uri': _STRING, 'uriBaseId': _TEXT, 'index': _INDEX,
                     'description': _MESSAGE, 'properties': {'type': 'object'}})
_SUPPRESSION = _object({
    'kind': {'enum': ['inSource', 'external']},
    'status': {'enum': ['accepted', 'underReview', 'rejected']},
    'justification': _STRING, 'properties': {'type': 'object'}}, ('kind',))
_RESULT = _object({
    'message': _MESSAGE, 'ruleId': _TEXT, 'ruleIndex': _INDEX,
    'provenance': _object({'invocationIndex': _INDEX}),
    'baselineState': {'enum': ['new', 'unchanged', 'updated', 'absent']},
    'suppressions': {'anyOf': [{'type': 'null'}, {'type': 'array', 'items': _SUPPRESSION}]},
    'properties': {'type': 'object'}})
_ARTIFACT = _object({
    'location': _LOCATION, 'length': _INDEX,
    'contents': _object({'text': _STRING, 'binary': _STRING}),
    'hashes': {'type': 'object', 'additionalProperties': _STRING},
    'properties': {'type': 'object'}})


def _check(value, schema, pointer, reason):
    try:
        validate_builtin(value, schema)
    except ModelError as error:
        raise EvidenceImportError(reason, pointer=pointer + error.pointer) from error


def _reference(value, size, pointer):
    if type(value) is not int or value < -1 or value >= size:
        raise EvidenceImportError('invalid_sarif_reference', pointer=pointer)
    return value


def validate_selected(run, row, result, candidate, rule, artifacts):
    """Reject inconsistent sources even when optional metadata is not imported.

    Absence from a baseline and suppression never stand in for a passing test.
    A selected invocation cannot replace an explicitly linked different one.
    Checking a reference does not implicitly include the referenced object.
    """
    run_pointer = '/runs/' + str(row['run_index'])
    pointer, value = result['pointer'], result['value']
    driver = run['tool']['driver']
    _check(driver, _object({'name': _TEXT, 'version': _STRING, 'semanticVersion': _STRING}),
           run_pointer + '/tool/driver', 'invalid_sarif_driver_metadata')
    _check(value, _RESULT, pointer, 'invalid_sarif_result_metadata')
    if value.get('baselineState') == 'absent':
        raise EvidenceImportError('sarif_baseline_only_result', pointer=pointer + '/baselineState')
    if candidate['result'] == 'passed' and value.get('suppressions'):
        raise EvidenceImportError('sarif_suppressed_pass_unsupported', pointer=pointer + '/suppressions')

    rules = driver.get('rules', [])
    # Existing explicit-rule checks retain their W diagnostics. Validate
    # references also when the caller chose not to import the related rule.
    if 'ruleIndex' in value:
        rule_index = _reference(value['ruleIndex'], len(rules), pointer + '/ruleIndex')
        if rule_index >= 0:
            descriptor = rules[rule_index]
            _check(descriptor, _object({'id': _TEXT}, ('id',)),
                   run_pointer + f'/tool/driver/rules/{rule_index}', 'invalid_sarif_rule_id')
            if 'ruleId' in value and value['ruleId'] != descriptor['id']:
                raise EvidenceImportError('sarif_rule_binding_mismatch', pointer=pointer)
    elif 'ruleId' in value and sum(r.get('id') == value['ruleId'] for r in rules) > 1:
        raise EvidenceImportError('ambiguous_sarif_rule_reference', pointer=pointer + '/ruleId')
    if rule is not None:
        _check(rule['value'], _object({
            'id': _TEXT, 'name': _STRING, 'messageStrings': {'type': 'object'},
            'properties': {'type': 'object'}}, ('id',)),
            rule['pointer'], 'invalid_sarif_rule_metadata')

    invocations = run.get('invocations', [])
    provenance = value.get('provenance', {})
    if 'invocationIndex' in provenance:
        if 'invocations' not in run:
            raise EvidenceImportError('invalid_sarif_reference',
                                      pointer=pointer + '/provenance/invocationIndex')
        linked = _reference(provenance['invocationIndex'], len(invocations),
                            pointer + '/provenance/invocationIndex')
    else:
        linked = 0 if len(invocations) == 1 else -1
    if linked >= 0:
        if row['invocation_index'] is not None and row['invocation_index'] != linked:
            raise EvidenceImportError('sarif_invocation_binding_mismatch',
                                      pointer=pointer + '/provenance')
        linked_pointer = run_pointer + '/invocations/' + str(linked)
        _check(invocations[linked], _object({'executionSuccessful': {'type': 'boolean'}},
                                           ('executionSuccessful',)),
               linked_pointer, 'invalid_sarif_invocation')
        if candidate['result'] == 'passed' and not invocations[linked]['executionSuccessful']:
            raise EvidenceImportError('sarif_failed_invocation_cannot_pass', pointer=linked_pointer)

    for artifact in artifacts:
        data, at = artifact['value'], artifact['pointer']
        _check(data, _ARTIFACT, at, 'invalid_sarif_artifact_metadata')
        if 'length' in data and type(data['length']) is not int:
            raise EvidenceImportError('invalid_sarif_artifact_metadata', pointer=at + '/length')
        location = data.get('location', {})
        if 'index' in location:
            index = _reference(location['index'], len(run.get('artifacts', [])), at + '/location/index')
            if index >= 0 and 'uri' in location:
                referred = run['artifacts'][index].get('location', {})
                if (type(referred) is not dict
                        or ('uri' in referred and location['uri'] != referred['uri'])
                        or location.get('uriBaseId') != referred.get('uriBaseId')):
                    raise EvidenceImportError('sarif_artifact_binding_mismatch', pointer=at + '/location')
