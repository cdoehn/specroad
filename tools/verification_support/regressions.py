"""Exact executable bindings for the first 47 normative contract regressions.

The inventory selects existing real tests; it neither calls test functions nor
turns their collection into execution. Original run bytes remain authoritative.
"""
from .common import CatalogError, read_object

REGRESSION_IDS = tuple('R-%02d' % i for i in range(1, 48))


def load_regressions(root, collection):
    path = root / 'verification/regressions.json'
    if not path.exists() and not path.is_symlink():
        return None
    value, digest = read_object(path)
    if (set(value) != {'format_version', 'specification_sha256', 'regressions'}
            or type(value['format_version']) is not int or value['format_version'] != 1
            or value['specification_sha256'] != collection['specification_sha256']
            or type(value['regressions']) is not list or len(value['regressions']) != 47):
        raise CatalogError('Invalid current R-01 to R-47 inventory')
    available = set(collection['nodeid_to_test_id'].values())
    for expected, row in zip(REGRESSION_IDS, value['regressions']):
        if (type(row) is not dict or set(row) != {'regression_id', 'requirement_id', 'verification_id', 'contract', 'test_ids'}
                or row['regression_id'] != expected or row['requirement_id'] != 'SR-REQ-0650'
                or row['verification_id'] != 'SR-VER-0041'
                or type(row['contract']) is not str or not row['contract'].strip()
                or type(row['test_ids']) is not list or not row['test_ids']
                or any(type(t) is not str or not t for t in row['test_ids'])
                or len(set(row['test_ids'])) != len(row['test_ids'])
                or not set(row['test_ids']) <= available):
            raise CatalogError('Regression needs exact current executable tests: ' + expected)
    return value, digest


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
