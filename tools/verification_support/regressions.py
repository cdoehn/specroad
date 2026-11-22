"""Exact executable bindings for the first 47 normative contract regressions.

The inventory selects existing real tests; it neither calls test functions nor
turns their collection into execution. Original run bytes remain authoritative.
"""
from .common import CatalogError
from .catalog_contract import validate_preflight_report
from .commit_tests import validate_plan
from .identity import source_identity
from pathlib import Path

from .regression_contract import REGRESSION_IDS, load_regressions


def regression_report(loaded, run_status, report):
    if loaded is None:
        return None
    value, digest = loaded
    rows = []
    for row in value['regressions']:
        outcomes = ({name: report['test_outcomes'][name] for name in row['test_ids']}
                    if run_status == 'current' else {})
        if run_status == 'current':
            status = ('failed' if any(v in ('failed', 'error', 'unexpected_success') for v in outcomes.values())
                      else 'passed' if all(v == 'passed' for v in outcomes.values()) else 'open')
        else:
            status = 'open' if run_status == 'not_supplied' else run_status
        rows.append({**row, 'status': status, 'test_outcomes': outcomes,
                     'evidence_id': report['run_id'] + '/' + row['regression_id'] if outcomes else None})
    return {'format_version': 1, 'purpose': 'contract_regression_inventory',
            'catalog_sha256': digest, 'specification_sha256': value['specification_sha256'],
            'regressions': rows, 'all_passed': all(r['status'] == 'passed' for r in rows),
            'counts': {s: sum(r['status'] == s for r in rows) for s in ('open', 'failed', 'passed', 'stale', 'invalid')},
            'release_approved': False}


def required_regression_plan(root, collection, commit_id):
    """Select the union once, unfiltered, using the existing Apply plan contract."""
    root = Path(root)
    source = source_identity(root)
    if not validate_preflight_report(root, collection, source):
        raise CatalogError('Current complete collection required for regression selection')
    loaded = load_regressions(root, collection)
    if loaded is None:
        raise CatalogError('No regression inventory; no complete regression gate')
    value, digest = loaded
    plan = {'format_version': 1, 'commit_id': commit_id,
            'test_ids': sorted({t for row in value['regressions'] for t in row['test_ids']}),
            'test_files': [],
            'reason': 'Complete R-01..R-47 regression union from current catalog ' + digest
                      + '; all exact variants mandatory, independent of runtime filter and rotation. '
                      'Collection is not execution; no human or release acceptance is inferred.'}
    if source_identity(root) != source:
        raise CatalogError('Regression inputs changed during selection')
    return validate_plan(plan, commit_id)
