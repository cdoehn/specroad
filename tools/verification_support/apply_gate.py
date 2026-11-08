"""Recheck a commit gate from its catalog, frozen measurements and observations."""
from hashlib import sha256
from pathlib import Path

from ._apply_registry import REGISTRY, select_partition, selection_receipt
from .apply_rotation import commit_context
from .ci_reference import _load_report
from .commit_tests import SCOPE, union_selection, validate_plan
from .common import json_bytes
from .identity import source_identity
from .runtime_history import filter_latest
from .selected_contract import verify_observation
from .host_execution import enabled, validate_resources, verify_resources


def verify_commit_gate(root, directory, *, source, head, test_plan):
    root, directory = Path(root), Path(directory)
    validate_plan(test_plan, test_plan.get('commit_id'))
    report = _load_report(directory / 'selection.json')
    catalog = _load_report(directory / 'catalog.json')
    snapshot_raw = (directory / 'runtime-snapshot.json').read_bytes()
    snapshot = _load_report(directory / 'runtime-snapshot.json')
    raw = (root / REGISTRY).read_bytes()
    registry = _load_report(root / REGISTRY)
    current, sequence, previous = commit_context(root, registry)
    pairs = catalog['nodeid_to_test_id']
    if (current != head or source_identity(root) != source
            or not catalog['catalog_valid'] or catalog['collection_exit_code'] != 0
            or catalog['errors'] or catalog['tests_run'] != 0 or catalog['source_sha256'] != source
            or catalog['collected_tests'] != len(pairs)
            or [r['test_id'] for r in snapshot['tests']] != sorted(pairs.values())
            or snapshot_raw != json_bytes(snapshot)):
        raise ValueError('Gate catalog, source, history or measurement snapshot changed')
    partition = select_partition(pairs, registry, sequence, previous)
    filtered, runtime = filter_latest(partition, snapshot, allow_empty=True)
    selected, required = union_selection(filtered, pairs, test_plan, runtime)
    resources = validate_resources(report["host_resources"]) if enabled(root) else None
    pool = report.get('host_pool')
    if pool is not None:
        from dev.test_hosts.pool import public_proof
        profile = _load_report(directory / 'host-run.json')
        if public_proof(profile) != pool or profile['source_sha256'] != source or profile['selected'] != selected:
            raise ValueError('Host run does not bind the current Apply selection')
    receipt = selection_receipt(registry, raw, selected, head, sequence, runtime, required, resources, pool)
    if (report['format_version'] != (5 if pool is not None else 4 if resources is not None else 3) or report['test_scope'] != SCOPE
            or report['selected_passed'] is not True or report['full_suite_passed'] is not None
            or report['source_sha256'] != source or report['base_commit'] != head
            or report['commit_id'] != test_plan['commit_id'] or report['commit_sequence'] != sequence
            or report['partition_count'] != 3 or report['partition_index'] != sequence % 3
            or report['anchor_commit'] != registry['anchor_commit']
            or report['rotation_anchor_commit'] != registry['rotation_anchor_commit']
            or report['expected_tests'] != len(selected) or report['collected_tests'] != len(pairs)
            or report['nodeid_to_test_id'] != selected or report['runtime_filter'] != runtime
            or report['required_tests'] != required or report['workers'] != (len(pool['workers']) if pool else resources['workers'] if resources else 4)
            or report['exit_code'] != 0 or report['process_exit_code'] != 0 or report['errors']
            or any(report[k] != v for k, v in receipt.items())):
        raise ValueError('The commit gate does not prove its exact rotation/required union')
    observation = _load_report(directory / 'observations.json')
    verify_observation(observation, {n.split('::', 1)[0] for n in selected}, len(selected))
    if pool is None:
        verify_resources(observation, resources)
    else:
        from dev.test_hosts.pool import verify_pool
        verify_pool(observation, pool)
    if (observation['nodeid_to_test_id'] != selected
            or any(not name.startswith('gw') for name in observation['worker_test_counts'])):
        raise ValueError('The commit gate has foreign test observations')
    return {'selection_sha256': receipt['selection_sha256'], 'tests': len(selected),
            'partition_index': sequence % 3, 'required_tests': len(required['nodeid_to_test_id']),
            'observations_sha256': sha256((directory / 'observations.json').read_bytes()).hexdigest()}
