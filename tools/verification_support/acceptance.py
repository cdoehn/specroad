"""Assemble current test bindings without executing tests or granting approval.

Inputs are trusted local runner reports, not authenticated foreign evidence.
One explicitly selected run is assessed; historical successes are never merged
or rewritten to fit a new specification, source, fixture or runtime binding.
"""
from pathlib import Path

from .catalog import load_catalog
from .catalog_contract import validate_preflight_report
from .common import CatalogError, json_bytes, read_object, sha256
from .evidence import current_evidence_status, validate_binding
from .identity import source_identity
from .outcomes import RANK


def _run_status(catalog, collection, source, binding, report):
    if report is None:
        if binding is not None:
            raise CatalogError('A selected run binding needs its original report')
        return 'not_supplied', {}
    validate_binding(binding)
    if type(report) is not dict:
        return 'invalid', {}
    if (binding['tool_build_sha256'] != source
            or any(report.get(k) != v for k, v in binding.items())
            or report.get('specification_sha256') != catalog.specification_sha256
            or report.get('catalog_sha256') != catalog.catalog_sha256):
        return 'stale', {}
    try:
        observed = report['observation']
        pairs = collection['nodeid_to_test_id']
        outcomes = report['test_outcomes']
        cases = report['cases']
        if (type(report['report_format_version']) is not int or report['report_format_version'] != 2
                or report['purpose'] != 'development_behavior_evidence'
                or report['release_approved'] is not False or report['release_gate'] != 'not_evaluated'
                or report['catalog_complete'] is not catalog.complete
                or type(observed) is not dict or type(outcomes) is not dict
                or type(observed['observation_format_version']) is not int
                or observed['observation_format_version'] != 1 or observed['engine'] != 'pytest'
                or type(observed['nodeids']) is not list
                or len(observed['nodeids']) != len(pairs) or set(observed['nodeids']) != set(pairs)
                or observed['nodeid_to_test_id'] != pairs
                or set(outcomes) != set(pairs.values()) or observed['test_outcomes'] != outcomes
                or any(type(v) is not str or v not in RANK for v in outcomes.values())
                or type(report['tests_run']) is not int or report['tests_run'] != len(pairs)
                or type(observed['tests_run']) is not int or observed['tests_run'] != len(pairs)
                or type(observed['pytest_exit_code']) is not int
                or observed['pytest_exit_code'] not in (0, 1)
                or type(cases) is not list or len(cases) != len(catalog.cases)
                or sha256(json_bytes(report['runtime'])) != binding['platform_sha256']
                or sha256(json_bytes(report['execution'])) != binding['configuration_sha256']):
            return 'invalid', {}
        counts = observed['worker_test_counts']
        workers = observed['workers']
        if (type(counts) is not dict or not counts
                or any(type(k) is not str or not k or type(v) is not int or v < 0 for k, v in counts.items())
                or sum(counts.values()) != len(pairs)
                or type(workers) is not list or workers != sorted(counts)
                or type(report['requirement_counts']) is not dict
                or any(type(v) is not int or v < 0 for v in report['requirement_counts'].values())):
            return 'invalid', {}
        runtime, execution = report['runtime'], report['execution']
        if (type(runtime) is not dict or set(runtime) != {'implementation', 'python', 'system', 'machine'}
                or any(type(v) is not str or not v for v in runtime.values())
                or type(execution) is not dict or execution.get('engine') != 'pytest'
                or type(execution.get('workers')) is not int or execution['workers'] < 1
                or execution.get('distribution') != 'worksteal'
                or execution.get('test_timeout', False) is not None
                or execution.get('suite_timeout', False) is not None):
            return 'invalid', {}
        # The native xdist observer records exitstatus=1 as worker_nonzero_exit
        # even for ordinary test failures. That is current negative evidence,
        # not a broken observation, only with the matching exit and outcomes.
        worker_test_failure = (observed['errors'] == ['worker_nonzero_exit']
            and observed['pytest_exit_code'] == 1
            and any(v in ('failed', 'error', 'unexpected_success') for v in outcomes.values()))
        if observed['errors'] != [] and not worker_test_failure:
            return 'invalid', {}
        passed = all(v == 'passed' for v in outcomes.values()) and observed['pytest_exit_code'] == 0
        if report['suite_passed'] is not passed or observed['suite_passed'] is not passed:
            return 'invalid', {}
        by_case = {item['test_case_id']: item for item in cases}
        if len(by_case) != len(cases) or set(by_case) != {c.data['test_case_id'] for c in catalog.cases}:
            return 'invalid', {}
        statuses = {}
        for case in catalog.cases:
            data = case.data
            evidence = by_case[data['test_case_id']]
            status = current_evidence_status(case, binding, evidence)
            if (status in ('stale', 'invalid') or evidence['test_outcomes'] !=
                    {name: outcomes[name] for name in data['test_ids']}):
                return 'invalid', {}
            statuses[data['test_case_id']] = status
        expected_counts = {s: sum(v == s for v in statuses.values())
                           for s in ('open', 'partial', 'failed', 'passed')}
        if report['requirement_counts'] != expected_counts:
            return 'invalid', {}
        return 'current', statuses
    except (KeyError, TypeError, ValueError, AttributeError, RecursionError):
        return 'invalid', {}


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
    status, outcomes = _run_status(catalog, collection, source, binding, report)
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
        'behavior_evidence_complete': catalog.complete and bool(rows) and all(r['status'] == 'passed' for r in rows),
        'original_specification_accepted': False, 'release_approved': False,
        'release_gate': 'not_evaluated',
    }
