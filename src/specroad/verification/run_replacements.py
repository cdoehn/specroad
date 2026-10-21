"""Bound human run-replacement decisions over the supplied immutable model.

This is a selection stage, not prioritized result aggregation or an execution
attestation. Original Evidence and the complete native assessment are retained.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from .evaluation import VerificationEvaluation, _replacement_order
from .run_assessment import assess_verification_runs
from ._required_keys import _key


@dataclass(frozen=True, init=False)
class VerificationReplacementAssessment:
    """Owned replacement disposition; no verification pass or write permission."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use assess_run_replacements')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Run replacements are not verification success or approval')


def assess_run_replacements(model, evaluation, *, configuration_id,
                            scope_descriptor=None, scope_bindings=None):
    """Apply only fully bound decisions to independently selected run candidates.

Human identity is an explicit caller declaration, not authentication. Input
bytes/roles, live inventory and project evaluation-ID history are separate gates.
No files, clocks, product code or external commands are accessed.
    """
    from ..changes.target_model import TargetModel
    if type(model) is not TargetModel:
        raise ModelError('verification_target_model_required')
    model = model.snapshot()
    assessment = assess_verification_runs(model, evaluation, configuration_id=configuration_id,
        scope_descriptor=scope_descriptor, scope_bindings=scope_bindings)
    evaluation = None if evaluation is None else VerificationEvaluation(evaluation.source_bytes)
    assessed = assessment.data
    eligible = assessed['run_selection_evaluated']
    selected = assessed['selection']
    decisions = [] if evaluation is None else evaluation.data['replacements']
    # Native selection has validated every Evidence record. The set binding
    # includes ALL records of a key/product/run, even excluded configurations:
    # an additional old observation must not disappear from the authorized set.
    records = [parse_json_object(document.content) for document in model.documents]
    evidence = [value for value in records if value['artifact_type'] == 'evidence']
    checks, diagnostics, missing = [], [], []
    if not eligible:
        diagnostics.extend(selected['coverage']['diagnostics'])
    for check in assessed['checks']:
        key = {field: check[field] for field in
               ('subject_artifact_id', 'contract_id', 'test_id', 'check_id')}
        rows = {row['replaced_run_id']: row for row in decisions if _key(row) == _key(key)}
        graph = {old: row['replacement_run_ids'] for old, row in rows.items()}
        runs = {row['run_id']: row for row in check['runs']}
        sets = {}
        required_subjects = {key['subject_artifact_id'], key['contract_id'], key['test_id']} - {None}
        for item in evidence:
            run = item['run_context']
            if (run is not None and run['run_id'] in rows
                    and run['subject_id'] == selected['evaluated_subject']['subject_id']
                    and run['subject_state_sha256'] == selected['evaluated_subject']['state_sha256']
                    and run['check_id'] == key['check_id'] and run['test_id'] == key['test_id']
                    and required_subjects <= {s['artifact_id'] for s in item['subjects']}):
                sets.setdefault(run['run_id'], []).append(
                    {'id': item['id'], 'sha256': canonical_json_sha256(item)})
        bound, observations = {}, {}
        for old, row in rows.items():
            items = sorted(sets.get(old, []), key=lambda item: item['id'].encode('utf-8'))
            actual_hash = canonical_json_sha256(items) if items else None
            bound[old] = actual_hash == row['replaced_evidence_set_sha256'] and bool(items)
            observations[old] = {'decision': row, 'evidence_set': items,
                'actual_evidence_set_sha256': actual_hash, 'evidence_set_matches': bound[old],
                'old_run_observed': bool(runs.get(old, {}).get('evidence'))}
        terminals, issues, terminal_checks = {}, {}, {}
        for run_id in _replacement_order(graph):
            if run_id not in graph:
                terminals[run_id] = {run_id}
                observed = runs.get(run_id, {}).get('evidence', [])
                reasons = []
                if not observed:
                    reasons.append('replacement_run_missing')
                else:
                    if any(e['freshness'] != 'current' for e in observed):
                        reasons.append('replacement_run_not_current')
                    if any(e['result'] not in ('passed', 'failed') for e in observed):
                        reasons.append('replacement_run_incomplete')
                issues[run_id] = {(run_id, reason) for reason in reasons}
                terminal_checks[run_id] = {'run_id': run_id,
                    'presence': 'present' if observed else 'missing',
                    'current_complete': not reasons, 'reasons': reasons,
                    'evidence': [{field: item[field] for field in
                        ('evidence_id', 'artifact_sha256', 'source_sha256', 'freshness', 'result')}
                        for item in observed]}
            else:
                terminals[run_id] = set().union(*(terminals[child] for child in graph[run_id]))
                issues[run_id] = set().union(*(issues[child] for child in graph[run_id]))
                if not bound[run_id]:
                    issues[run_id].add((run_id, 'replaced_evidence_set_changed'))
                # A hash of excluded records cannot satisfy an absent required
                # candidate (including an intermediate run in a replacement chain).
                if not observations[run_id]['old_run_observed']:
                    issues[run_id].add((run_id, 'replaced_run_missing'))
        effective = {old for old in rows if not issues[old]}
        replacements = []
        for old in rows:
            details = [{'run_id': run_id, 'reason': reason} for run_id, reason in
                       sorted(issues[old], key=lambda pair: tuple(s.encode('utf-8') for s in pair))]
            replacements.append({**observations[old], 'effective': old in effective,
                'terminal_run_ids': sorted(terminals[old], key=lambda s: s.encode('utf-8')),
                'terminal_runs': [terminal_checks[run_id]
                    for run_id in sorted(terminals[old], key=lambda s: s.encode('utf-8'))],
                'binding_issues': details})
            if details:
                diagnostics.append({'code': 'SRV176', 'severity': 'warning',
                    'reason': 'replacement_binding_changed', **key, 'replaced_run_id': old,
                    'binding_issues': details})
        expected = set()
        for run_id in check['expected_run_ids']:
            expected.update(terminals[run_id] if run_id in effective else {run_id})
        active = set(runs) - effective
        for old in effective:
            active.update(terminals[old])
        for run_id in sorted(expected, key=lambda s: s.encode('utf-8')):
            if not runs.get(run_id, {}).get('evidence'):
                row = {**key, 'run_id': run_id}
                missing.append(row)
                diagnostics.append({'code': 'SRV176', 'severity': 'warning',
                                    'reason': 'required_run_missing', **row})
        checks.append({**key, 'expected_run_ids': check['expected_run_ids'],
            'effective_expected_run_ids': sorted(expected, key=lambda s: s.encode('utf-8')),
            'active_run_ids': sorted(active, key=lambda s: s.encode('utf-8')),
            'superseded_run_ids': sorted(effective, key=lambda s: s.encode('utf-8')),
            'replacements': replacements})
    incomplete = not eligible or bool(diagnostics)
    report = {'format_version': 'verification-run-replacements-v1',
        'validation_scope': 'supplied_model_run_replacements',
        'assessment': assessed, 'assessment_sha256': assessment.sha256,
        'project_id': assessed['project_id'], 'input_sha256': assessed['input_sha256'],
        'evaluation_sha256': assessed['evaluation_sha256'],
        'checks': checks, 'missing_runs': missing, 'diagnostics': diagnostics,
        'assessment_status': 'incomplete' if incomplete else 'assessed',
        'verification_result': 'incomplete' if incomplete else None,
        'run_replacements_evaluated': eligible, 'human_identity_authenticated': False,
        'input_bytes_verified': False, 'input_roles_verified': False, 'project_files_verified': False,
        'project_required_checks_complete': False, 'result_aggregation_evaluated': False,
        'full_verification_evaluated': False, 'external_run_verified': False,
        'release_readiness_evaluated': False, 'test_code_executed': False,
        'write_authorized': False, 'approval_granted': False}
    result = object.__new__(VerificationReplacementAssessment)
    object.__setattr__(result, '_encoded', canonical_json_bytes(report))
    return result
