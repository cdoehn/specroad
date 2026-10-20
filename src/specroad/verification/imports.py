"""Passive JUnit, Generic and SARIF preparation with explicit import policy.

Preparing an import neither publishes Evidence nor authenticates a run or tool.
"""
from dataclasses import dataclass
from hashlib import sha256

from .._metadata import __version__
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.record_schemas import record_schema
from ._import_candidates import CandidateValue, passive_status
from .evidence_exchange import EvidenceImportError, _encode_candidates, _read_json, _validate
from .junit import JUnitDocument
from .junit_mapping import (JUnitMapping, JUnitMappingRules, JUnitMappingError,
    JUnitExternalIdentifiers, analyze_junit_candidates)
from .evidence_exchange import (EvidenceExchange, evidence_exchange_schema, _read_exchange,
    _targets, _result_bindings, _generic_candidate, _unique)
from .sarif import SarifDocument, SarifMapping, _mapping_schema, _sarif_candidate


@dataclass(frozen=True, init=False)
class EvidenceImportPreparation(CandidateValue):
    """An immutable decision and its original files, without write authority."""
    _encoded: bytes
    _originals: tuple

    def __init__(self, *args, **kwargs):
        raise TypeError('Use an import preparation adapter with owned inputs')

    @property
    def original_files(self):
        """Detached role-to-bytes map; these are not paths or published files."""
        return dict(self._originals)

    def __bool__(self):
        raise TypeError('Import preparation is not successful verification or write authority')


def _original(raw):
    return {'sha256': sha256(raw).hexdigest(), 'size': len(raw)}


def _tool(value):
    if type(value) is not dict:
        raise EvidenceImportError('explicit_import_tool_required', pointer='/tool')
    try:
        definitions = record_schema('evidence')['$defs']
        _validate(value, {'$ref': '#/$defs/tool', '$defs': definitions})
        return _read_json(canonical_json_bytes(value))
    except ModelError as error:
        raise EvidenceImportError(error.reason, pointer='/tool' + error.pointer) from error


def prepare_junit_import(document, mapping, *, targets, policy, tool,
                         external_identifiers=None):
    """Bind originals and apply abort/skip to every diagnosed JUnit occurrence.

    ``abort_import`` withholds all candidates when any mapping diagnostic is
    present. ``skip_invalid_with_diagnostic`` retains only independently valid
    candidates and all diagnoses. Failed or skipped test outcomes are valid
    observations, not malformed evidence. Global input errors still raise.
    """
    if type(policy) is not str or policy not in ('abort_import', 'skip_invalid_with_diagnostic'):
        raise EvidenceImportError('explicit_import_policy_required', pointer='/policy')
    tool = _tool(tool)
    if type(document) is not JUnitDocument:
        raise JUnitMappingError('typed_junit_document_required')
    if type(mapping) not in (JUnitMapping, JUnitMappingRules):
        raise JUnitMappingError('typed_junit_mapping_required')
    if external_identifiers is not None and type(external_identifiers) is not JUnitExternalIdentifiers:
        raise JUnitMappingError('typed_junit_external_identifiers_required')
    # Own all source bytes before analysis; replaceable decoded caches cannot
    # substitute a different report, mapping, sidecar or provenance descriptor.
    document, mapping = JUnitDocument(document.source_bytes), type(mapping)(mapping.source_bytes)
    sidecar = (None if external_identifiers is None
               else JUnitExternalIdentifiers(external_identifiers.source_bytes))
    analysis = analyze_junit_candidates(
        document, mapping, targets=targets, external_identifiers=sidecar)
    observed = analysis.data
    originals = [('source', document.source_bytes), ('mapping', mapping.source_bytes)]
    external = None
    if sidecar is not None:
        originals.append(('external_identifiers', sidecar.source_bytes))
        external = {**_original(sidecar.source_bytes), 'canonical_sha256': sidecar.sha256,
                    'format_version': sidecar.data['format_version']}
    provenance = {
        'format_version': 'evidence-import-provenance-v1', 'import_format': 'junit',
        'source': _original(document.source_bytes),
        'mapping': {**_original(mapping.source_bytes), 'canonical_sha256': mapping.sha256,
                    'format_version': mapping.data['format_version']},
        'external_identifiers': external, 'parser_profile': observed['parser_profile'],
        'tool': tool, 'importer': {'name': 'specroad', 'version': __version__}}
    provenance_hash = canonical_json_sha256(provenance)
    aborted = policy == 'abort_import' and bool(observed['diagnostics'])
    candidates = [] if aborted else [
        {**candidate, 'provenance_sha256': provenance_hash} for candidate in observed['candidates']]
    value = {
        'format_version': 'evidence-import-preparation-v1', 'import_format': 'junit',
        'policy': policy, 'decision': 'aborted' if aborted else 'prepared',
        'provenance': provenance, 'provenance_sha256': provenance_hash,
        'analysis_sha256': analysis.sha256, 'candidates': candidates,
        'candidate_count': len(candidates), 'testcase_count': observed['testcase_count'],
        'diagnostics': observed['diagnostics'],
        'rejected_testcase_indexes': observed['rejected_testcase_indexes'],
        'withheld_testcase_indexes': (
            [candidate['testcase_index'] for candidate in observed['candidates']] if aborted else []),
        **passive_status(import_policy_applied=True, run_context_bound=False,
                         producer_tool_verified=False)}
    prepared = object.__new__(EvidenceImportPreparation)
    object.__setattr__(prepared, '_encoded', _encode_candidates(value))
    object.__setattr__(prepared, '_originals', tuple(originals))
    return prepared


def _policy(policy):
    if type(policy) is not str or policy not in ('abort_import', 'skip_invalid_with_diagnostic'):
        raise EvidenceImportError('explicit_import_policy_required', pointer='/policy')


def _input_bytes(value, kind):
    if type(value) is kind:
        value = value.source_bytes
    if type(value) is not bytes:
        raise EvidenceImportError('typed_import_or_bytes_required')
    return value


def _charge(value, budget):
    """Bound retained output incrementally, before repeated metadata expands."""
    stack = [value]
    while stack:
        item = stack.pop()
        budget[0] += 1
        if type(item) is dict:
            stack.extend(item.keys())
            stack.extend(item.values())
        elif type(item) is list:
            stack.extend(item)
        elif type(item) is str:
            budget[1] += len(item.encode('utf-8'))
        if budget[0] > 100000 or budget[1] > 16 * 1024 * 1024:
            raise EvidenceImportError('evidence_import_candidate_limit')


def _generic_analysis(raw, targets):
    value = _read_json(raw)
    schema = evidence_exchange_schema()
    # The global envelope remains strict. Individual records are validated
    # separately so one malformed required field is an explained omission.
    _validate(value, {**schema, 'properties': {
        **schema['properties'], 'results': {'type': 'array'}}})
    _read_exchange(canonical_json_bytes({**value, 'results': []}))
    bindings, native_subjects = _targets(targets)
    subjects = {s['artifact_id']: s for s in value['subjects']}
    attachments = {a['path']: a for a in value['attachments']}
    subject_ids, attachment_paths = set(subjects), set(attachments)
    diagnostics, candidates, rejected, budget = [], [], set(), [0, 0]

    def diagnose(error, indices):
        diagnostic = {**error.diagnostic(), 'result_indexes': sorted(indices)}
        _charge(diagnostic, budget)
        diagnostics.append(diagnostic)
        rejected.update(indices)

    item_schema = {**schema['properties']['results']['items'], '$defs': schema['$defs']}
    valid, subject_results = {}, {}
    for number, result in enumerate(value['results']):
        pointer = '/results/' + str(number)
        try:
            _validate(result, item_schema)
        except EvidenceImportError as error:
            diagnose(EvidenceImportError(error.reason, pointer=pointer + error.pointer), [number])
            continue
        try:
            _result_bindings(result, subject_ids, attachment_paths, pointer)
        except EvidenceImportError as error:
            diagnose(error, [number])
            continue
        valid[number] = result
        for identity in result['subject_ids']:
            subject_results.setdefault(identity, []).append(number)
    for number, subject in enumerate(value['subjects']):
        if native_subjects.get(subject['artifact_id']) != subject:
            affected = subject_results.get(subject['artifact_id'], [])
            diagnose(EvidenceImportError('import_subject_binding_mismatch',
                                         pointer='/subjects/' + str(number)), affected)

    # Contradictory declarations for the same explicit slot cannot select the
    # favorable observation, even if a different required field is malformed.
    identity_fields = ('target_id', 'check_id', 'test_id', 'subject_ids', 'result')
    identity_schema = {**item_schema, 'properties': {
        k: item_schema['properties'][k] for k in identity_fields}, 'required': list(identity_fields)}
    groups = {}
    for number, result in enumerate(value['results']):
        if type(result) is not dict:
            continue
        identity = {k: result[k] for k in identity_fields if k in result}
        try:
            _validate(identity, identity_schema)
        except EvidenceImportError:
            continue
        key = (result['target_id'], result['check_id'], result['test_id'],
               tuple(sorted(set(result['subject_ids']))))
        groups.setdefault(key, []).append((number, result['result']))
    for group in groups.values():
        if len({outcome for _, outcome in group}) > 1:
            indices = [n for n, _ in group]
            diagnose(EvidenceImportError('conflicting_import_results',
                                         pointer='/results/' + str(indices[0])), indices)
    for number, result in valid.items():
        if number in rejected:
            continue
        try:
            candidate = _generic_candidate(value, result, number, bindings, subjects, attachments)
        except EvidenceImportError as error:
            diagnose(error, [number])
        else:
            _charge(candidate, budget)
            candidates.append(candidate)
    return value, candidates, diagnostics


def _prepare_records(format_name, originals, mapping, profile, tool, candidates,
                     diagnostics, occurrences):
    accepted = [c['source_pointer'] for c in candidates]
    rejected = {p for d in diagnostics for p in d['occurrences']}
    if (len(accepted) != len(set(accepted)) or set(accepted) & rejected
            or set(accepted) | rejected != set(occurrences)):
        raise EvidenceImportError('import_occurrence_accounting_mismatch')
    provenance = {
        'format_version': 'evidence-import-provenance-v1', 'import_format': format_name,
        'source': _original(originals[0][1]), 'mapping': mapping,
        'external_identifiers': None, 'parser_profile': profile, 'tool': tool,
        'importer': {'name': 'specroad', 'version': __version__}}
    analysis = {'candidates': candidates, 'diagnostics': diagnostics, 'occurrences': occurrences}
    return provenance, analysis


def prepare_generic_import(exchange, *, targets, policy):
    """Prepare exact Exchange bytes; record-local errors obey the given policy.

    Accept an existing EvidenceExchange or original bytes, including records
    whose missing/invalid required fields must be diagnosed individually.
    Global envelope, target and resource errors remain fatal for either policy.
    The Exchange itself contains the explicit target/check/test/subject mapping.
    """
    _policy(policy)
    raw = _input_bytes(exchange, EvidenceExchange)
    value, candidates, diagnostics = _generic_analysis(raw, targets)
    originals = [('source', raw)]
    mapping = {**_original(raw), 'canonical_sha256': canonical_json_sha256(value),
               'format_version': value['format_version'], 'source_role': 'source'}
    for candidate in candidates:
        candidate['source_pointer'] = '/results/' + str(candidate['result_index'])
    for diagnostic in diagnostics:
        diagnostic.update(input_role='source', occurrences=[
            '/results/' + str(n) for n in diagnostic['result_indexes']])
    occurrences = ['/results/' + str(n) for n in range(len(value['results']))]
    provenance, analysis = _prepare_records('generic', originals, mapping,
        value['format_version'], value['tool'], candidates, diagnostics, occurrences)
    provenance_hash = canonical_json_sha256(provenance)
    aborted = policy == 'abort_import' and bool(diagnostics)
    rejected = {p for d in diagnostics for p in d['occurrences']}
    data = {
        'format_version': 'evidence-import-preparation-v1', 'import_format': 'generic',
        'policy': policy, 'decision': 'aborted' if aborted else 'prepared',
        'provenance': provenance, 'provenance_sha256': provenance_hash,
        'analysis_sha256': sha256(_encode_candidates(analysis)).hexdigest(),
        'occurrences': occurrences, 'rejected_occurrences': [p for p in occurrences if p in rejected],
        'withheld_occurrences': [c['source_pointer'] for c in candidates] if aborted else [],
        'candidates': [] if aborted else [{**c, 'provenance_sha256': provenance_hash} for c in candidates],
        'candidate_count': 0 if aborted else len(candidates), 'diagnostics': diagnostics,
        **passive_status(import_policy_applied=True, run_context_bound=False,
            producer_tool_verified=False, external_run_verified=False,
            configuration_verified=False, attachments_verified=False, contract_slots_verified=False)}
    prepared = object.__new__(EvidenceImportPreparation)
    object.__setattr__(prepared, '_encoded', _encode_candidates(data))
    object.__setattr__(prepared, '_originals', tuple(originals))
    return prepared


def _sarif_position(row, parsed):
    if type(row) is not dict:
        return None
    r, i = row.get('run_index'), row.get('result_index')
    if (type(r) is int and type(i) is int and 0 <= r < len(parsed['runs'])
            and 0 <= i < len(parsed['runs'][r].get('results', []))):
        return f'/runs/{r}/results/{i}'
    return None


def prepare_sarif_import(document, mapping, *, targets, policy):
    """Prepare mapped inline observations; diagnose every omitted occurrence.

    Typed inputs or original bytes are accepted. Ambiguous/invalid mapping
    rows, invalid required Exchange records and selected SARIF errors are
    collected without letting any one of them select a favorable observation.
    """
    _policy(policy)
    raw = _input_bytes(document, SarifDocument)
    mapping_raw = _input_bytes(mapping, SarifMapping)
    document = SarifDocument(raw)
    parsed, settings = _read_json(raw), _read_json(mapping_raw)
    schema = _mapping_schema()
    _validate(settings, {**schema, 'properties': {
        **schema['properties'], 'exchange': {'type': 'object'}, 'bindings': {'type': 'array'}}})
    if settings['source_sha256'] != document.sha256:
        raise EvidenceImportError('sarif_source_binding_mismatch', pointer='/source_sha256')
    try:
        exchange, generic, generic_diagnostics = _generic_analysis(
            canonical_json_bytes(settings['exchange']), targets)
    except EvidenceImportError as error:
        prefix = '' if error.pointer.startswith('/targets') else '/exchange'
        raise EvidenceImportError(error.reason, pointer=prefix + error.pointer) from error
    generic = {c['result_index']: c for c in generic}
    occurrences = [f'/runs/{r}/results/{i}' for r, run in enumerate(parsed['runs'])
                   for i in range(len(run.get('results', [])))]
    occurrence_order = {p: n for n, p in enumerate(occurrences)}
    diagnostics, candidates, rejected, budget = [], [], set(), [0, 0]
    positions, indices, valid_rows = {}, {}, {}

    def diagnose(error, affected, role, **extra):
        pointers = sorted((p for p in affected if p in occurrence_order), key=occurrence_order.get)
        diagnostic = {**error.diagnostic(), 'input_role': role, 'occurrences': pointers, **extra}
        _charge(diagnostic, budget)
        diagnostics.append(diagnostic)
        rejected.update(pointers)

    row_schema = {**schema['properties']['bindings']['items'], '$defs': schema['$defs']}
    for number, row in enumerate(settings['bindings']):
        position = _sarif_position(row, parsed)
        if position is not None:
            positions.setdefault(position, []).append(number)
        index = row.get('exchange_result_index') if type(row) is dict else None
        if type(index) is int and 0 <= index < len(exchange['results']):
            indices.setdefault(index, []).append(number)
        pointer = '/bindings/' + str(number)
        try:
            _validate(row, row_schema)
            values = [row[k] for k in ('exchange_result_index', 'run_index', 'result_index',
                                       'rule_index', 'invocation_index')]
            if any(v is not None and type(v) is not int for v in values + row['artifact_indices']):
                raise EvidenceImportError('integer_sarif_index_required')
            _unique(row['artifact_indices'], '/artifact_indices')
            if position is None or row['exchange_result_index'] >= len(exchange['results']):
                raise EvidenceImportError('sarif_index_out_of_range')
        except EvidenceImportError as error:
            diagnose(EvidenceImportError(error.reason, pointer=pointer + error.pointer),
                     {position}, 'mapping', binding_indexes=[number])
        else:
            valid_rows[number] = row
    for position, rows in positions.items():
        if len(rows) > 1:
            diagnose(EvidenceImportError('ambiguous_sarif_result_mapping', pointer='/bindings'),
                     {position}, 'mapping', binding_indexes=rows)
    for index, rows in indices.items():
        if len(rows) > 1:
            affected = {_sarif_position(settings['bindings'][n], parsed) for n in rows}
            diagnose(EvidenceImportError('ambiguous_sarif_exchange_mapping', pointer='/bindings'),
                     affected, 'mapping', binding_indexes=rows, result_indexes=[index])
    for index in range(len(exchange['results'])):
        if index not in indices:
            diagnose(EvidenceImportError('sarif_exchange_mapping_incomplete',
                                         pointer='/exchange/results/' + str(index)),
                     set(), 'mapping', result_indexes=[index])
    for diagnostic in generic_diagnostics:
        affected = {_sarif_position(settings['bindings'][n], parsed)
                    for index in diagnostic['result_indexes'] for n in indices.get(index, [])}
        diagnose(EvidenceImportError(diagnostic['reason'], pointer='/exchange' + diagnostic['pointer']),
                 affected, 'mapping', result_indexes=diagnostic['result_indexes'])
    for position in occurrences:
        if position not in positions:
            diagnose(EvidenceImportError('unmapped_sarif_result', pointer=position),
                     {position}, 'source')
    for number, row in valid_rows.items():
        position = _sarif_position(row, parsed)
        if position in rejected:
            continue
        # A missing candidate already has a record-local diagnostic above.
        if row['exchange_result_index'] not in generic:
            continue
        try:
            candidate = _sarif_candidate(parsed, row, generic[row['exchange_result_index']])
        except EvidenceImportError as error:
            diagnose(error, {position}, 'source', binding_indexes=[number])
        else:
            candidate['source_pointer'] = position
            _charge(candidate, budget)
            candidates.append(candidate)
    originals = [('source', raw), ('mapping', mapping_raw)]
    mapping_binding = {**_original(mapping_raw), 'canonical_sha256': canonical_json_sha256(settings),
                       'format_version': settings['format_version']}
    provenance, analysis = _prepare_records('sarif', originals, mapping_binding,
        'sarif-inline-2.1.0-v1', exchange['tool'], candidates, diagnostics, occurrences)
    provenance_hash = canonical_json_sha256(provenance)
    aborted = policy == 'abort_import' and bool(diagnostics)
    data = {
        'format_version': 'evidence-import-preparation-v1', 'import_format': 'sarif',
        'policy': policy, 'decision': 'aborted' if aborted else 'prepared',
        'provenance': provenance, 'provenance_sha256': provenance_hash,
        'analysis_sha256': sha256(_encode_candidates(analysis)).hexdigest(),
        'occurrences': occurrences, 'rejected_occurrences': [p for p in occurrences if p in rejected],
        'withheld_occurrences': [c['source_pointer'] for c in candidates] if aborted else [],
        'candidates': [] if aborted else [{**c, 'provenance_sha256': provenance_hash} for c in candidates],
        'candidate_count': 0 if aborted else len(candidates), 'diagnostics': diagnostics,
        **passive_status(import_policy_applied=True, run_context_bound=False,
            producer_tool_verified=False, external_run_verified=False,
            configuration_verified=False, attachments_verified=False, contract_slots_verified=False)}
    prepared = object.__new__(EvidenceImportPreparation)
    object.__setattr__(prepared, '_encoded', _encode_candidates(data))
    object.__setattr__(prepared, '_originals', tuple(originals))
    return prepared
