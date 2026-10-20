"""Source interpretation and occurrence diagnostics, independent of import policy.

The collectors retain every source position and bounded diagnostic. They never
choose abort versus skip, bind preparation output or grant publication authority.
"""
from ..model.canonical import canonical_json_bytes
from .evidence_exchange import (
    EvidenceImportError, evidence_exchange_schema, _read_exchange, _read_json,
    _validate, _targets, _result_bindings, _generic_candidate, _unique)
from .sarif import SarifDocument, _mapping_schema, _sarif_candidate


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


def _sarif_position(row, parsed):
    if type(row) is not dict:
        return None
    r, i = row.get('run_index'), row.get('result_index')
    if (type(r) is int and type(i) is int and 0 <= r < len(parsed['runs'])
            and 0 <= i < len(parsed['runs'][r].get('results', []))):
        return f'/runs/{r}/results/{i}'
    return None


def _sarif_analysis(raw, mapping_raw, targets):
    """Collect inline SARIF candidates and diagnostics without a policy decision."""
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
    return settings, exchange, candidates, diagnostics, occurrences
