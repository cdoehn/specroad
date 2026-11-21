"""Assemble current test bindings without executing tests or granting approval.

Inputs are trusted local runner reports, not authenticated foreign evidence.
One explicitly selected run is assessed; historical successes are never merged
or rewritten to fit a new specification, source, fixture or runtime binding.
"""
from pathlib import Path

from .catalog import load_catalog
from .catalog_contract import validate_preflight_report
from .common import CatalogError, json_bytes, read_object, sha256
from .acceptance_evidence import selected_run_status
from .regressions import load_regressions, regression_report
from .identity import source_identity


def assemble_acceptance(root, collection, *, binding=None, report=None):
    """Return the exact inventory and honest evidence state for every case.

Collection and complete mapping are not execution. Missing and stale evidence,
incomplete implementation, TD-001 and human decisions retain separate states.
This report is a development inventory, never a release authorization.
"""
    root = Path(root)
    source = source_identity(root)
    if not validate_preflight_report(root, collection, source):
        raise CatalogError('Current complete native collection is required')
    catalog = load_catalog(root / 'verification')
    index, _ = read_object(root / 'verification/catalog.json')
    _, fixture_hash = read_object(root / 'verification/fixtures.json')
    regressions = load_regressions(root, collection)
    status, outcomes = selected_run_status(catalog, collection, source, binding, report)
    nodes = {v: k for k, v in collection['nodeid_to_test_id'].items()}
    rows = []
    mapped = set()
    for case in catalog.cases:
        data = case.data
        ids = data['test_ids']
        mapped.update(ids)
        excluded = data.get('policy_excluded_scope', [])
        policy = data.get('not_automated_by_user_policy')
        rows.append({
            'test_case_id': data['test_case_id'], 'requirement_id': data['requirement_id'],
            'primary_verification_id': data['primary_verification_id'],
            'manifest_sha256': case.manifest_sha256, 'fixture_ids': data['fixture_ids'],
            'implementation_status': data['implementation_status'], 'method': data['method'],
            'test_ids': ids, 'nodeids': [nodes[name] for name in ids],
            'status': outcomes.get(data['test_case_id'], 'open' if status == 'not_supplied' else status),
            'evidence_id': (binding['run_id'] + '/' + data['test_case_id']) if status == 'current' and ids else None,
            'not_automated_by_user_policy': policy, 'policy_excluded_scope': excluded,
            'excluded_scope_status': 'not_automated_by_user_policy' if policy or excluded else None,
            'original_requirement_accepted': False,
            'open_items': data['open_items'],
        })
    if (source_identity(root) != source or load_catalog(root / 'verification') != catalog
            or not validate_preflight_report(root, collection, source)):
        raise CatalogError('Acceptance inputs changed during assembly')
    return {
        'format_version': 1, 'purpose': 'development_acceptance_inventory',
        'source_sha256': source, 'specification_sha256': catalog.specification_sha256,
        'catalog_sha256': catalog.catalog_sha256, 'fixture_registry_sha256': fixture_hash,
        'collection_sha256': sha256(json_bytes(collection)),
        'evidence_sha256': sha256(json_bytes(report)) if report is not None else None,
        'selected_run': dict(binding) if binding is not None else None, 'run_status': status,
        'catalog_complete': catalog.complete, 'mapped_requirements': len(rows),
        'collected_tests': len(nodes), 'mapped_tests': len(mapped),
        'unmapped_test_ids': sorted(set(nodes) - mapped), 'cases': rows,
        'requirement_counts': {s: sum(r['status'] == s for r in rows)
                               for s in ('open', 'partial', 'failed', 'passed', 'stale', 'invalid')},
        'automation_policy': index.get('automation_policy'),
        'regressions': regression_report(regressions, status, report),
        'behavior_evidence_complete': catalog.complete and bool(rows) and all(r['status'] == 'passed' for r in rows),
        'original_specification_accepted': False, 'release_approved': False,
        'release_gate': 'not_evaluated',
    }
