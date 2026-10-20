"""Pure policy decisions over completed, source-specific analyses.

Keep diagnosis generation and global input errors in the format adapters.
These functions preserve diagnoses and only select or withhold valid candidates.
"""
from hashlib import sha256

from ..model.canonical import canonical_json_sha256
from ._import_candidates import passive_status
from .evidence_exchange import EvidenceImportError, _encode_candidates


def _policy(policy):
    if type(policy) is not str or policy not in ('abort_import', 'skip_invalid_with_diagnostic'):
        raise EvidenceImportError('explicit_import_policy_required', pointer='/policy')


def _junit_policy(observed, provenance, analysis, policy):
    """Retain the established testcase-index preparation contract."""
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
    return value


def _record_policy(format_name, provenance, analysis, policy):
    """Use the same occurrence-pointer decision for Generic and SARIF."""
    candidates = analysis['candidates']
    diagnostics = analysis['diagnostics']
    occurrences = analysis['occurrences']
    provenance_hash = canonical_json_sha256(provenance)
    aborted = policy == 'abort_import' and bool(diagnostics)
    rejected = {p for d in diagnostics for p in d['occurrences']}
    data = {
        'format_version': 'evidence-import-preparation-v1', 'import_format': format_name,
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
    return data
