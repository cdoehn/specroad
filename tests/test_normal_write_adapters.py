"""Real normal adapters use one interruption guard and complete v2 receipts."""
import json
from unittest.mock import patch

import pytest

from specroad.changes import PublicationAuthority, project_lock, read_transaction_completion
from specroad.changes.write_guard_values import MARKER_PATH, validate_transaction
from specroad.model.errors import ModelError
from specroad.cli.results import OperationFailure
from specroad.storage.project import ProjectSource
from support.authoring_execution import KINDS, scenario
from support.read_only import inventory, no_write_attempts

SPECIALISTS = ('baseline', 'evidence', 'measurement-import', 'import', 'format',
               'proposal-start', 'proposal-review', 'proposal-negative', 'proposal-apply')
ALLOW = PublicationAuthority('adapter-test-host', '1', lambda request: True)


def adapter(root, kind):
    if kind in KINDS:
        _, _, _, options, direct, entropy = scenario(root, kind)
        def run(authority):
            with patch('secrets.token_bytes', return_value=entropy):
                return direct({**options, 'transaction_id': 'normal-adapter', 'authority': authority})
    elif kind in ('baseline', 'evidence', 'measurement-import'):
        if kind == 'baseline':
            from test_baseline_creation import project, plan_for, apply
            model = project(root); plan = plan_for(model)
        elif kind == 'evidence':
            from test_evidence_recording import project, measurement, plan_for, apply
            model = project(root); plan = plan_for(model, measurement(model))
        else:
            from test_evidence_import_transaction import import_project, saved, apply
            model = import_project(root); plan = saved(model)
        def run(authority): return apply(plan, model, authority=authority)
    elif kind == 'import':
        from support.import_execution import project, candidates, inputs
        from specroad.exchange import apply_import_plan
        model, resource = project(root)
        def run(authority):
            return apply_import_plan(model, candidates(), **inputs(resource),
                transaction_id='normal-import', authority=authority)
    elif kind == 'format':
        from support.normalization_scope import prepared, GATES
        from support.publication import options
        from specroad.changes.guarded_write import publish_guarded_change
        _, _, preflight = prepared(root)
        (root / '.specroad/locks').mkdir(parents=True, exist_ok=True)
        def run(authority):
            with project_lock(root, **options(preflight)) as held:
                return publish_guarded_change(preflight, held_lock=held, authority=authority, gates=GATES)
    elif kind == 'proposal-apply':
        from support.proposal_apply import ApplyCase
        case = ApplyCase(root)
        def run(authority): return case.apply(authority=authority)
    else:
        from support.proposal_decisions import ReviewCase
        from specroad.proposals.review_start import review_start_project
        from specroad.proposals.review_decision import review_project
        case = ReviewCase(root, start=kind != 'proposal-start', minimum=1)
        if kind == 'proposal-start':
            def run(authority):
                return review_start_project(root, case.original.data['id'], expected_revision=1,
                    actor={'actor_type': 'human', 'actor_id': 'adapter-author'},
                    planned_at='2026-11-11T01:00:00Z', change_plan_id='adapter-start',
                    transaction_id='adapter-start', authority=authority)
        else:
            if kind == 'proposal-negative': case.decide()
            def run(authority):
                options = case.options(authority=authority)
                if kind == 'proposal-negative': options['decision'] = 'withdrawn'
                return review_project(root, case.original.data['id'], **options)
    # Own the otherwise harmless empty lock parent before the no-effect oracle.
    (root / ".specroad/locks").mkdir(parents=True, exist_ok=True)
    return run


@pytest.mark.parametrize('kind', (*KINDS, *SPECIALISTS))
def test_each_normal_adapter_has_one_complete_guarded_effect(tmp_path, kind):
    root = tmp_path / 'project'; run = adapter(root, kind)
    old = set(root.glob('.specroad/transactions/receipts/*/transaction.json'))
    run(ALLOW)
    new = set(root.glob('.specroad/transactions/receipts/*/transaction.json')) - old
    assert len(new) == 1
    write = validate_transaction(new.pop().read_bytes())
    assert write['files'] and write['validation']['model_valid']
    assert not (root / MARKER_PATH).exists()
    assert not (root / '.specroad/locks/project.json').exists()
    for row in write['files']:
        assert row['after'] is not None
        raw = (root / row['path']).read_bytes()
        from hashlib import sha256
        assert {'size': len(raw), 'sha256': sha256(raw).hexdigest()} == row['after']
    before = inventory(root)
    with no_write_attempts():
        proof = read_transaction_completion(ProjectSource(root), write['marker']['transaction_id']).data
    assert proof['commit_completed'] and proof['receipt_verified'] and not proof['current_target_verified']
    assert inventory(root) == before


@pytest.mark.parametrize('kind', (*KINDS, *SPECIALISTS))
@pytest.mark.parametrize('state', ('denied', 'blocked'))
def test_each_normal_adapter_refuses_without_modifying_originals(tmp_path, kind, state):
    root = tmp_path / 'project'; run = adapter(root, kind)
    if state == 'blocked':
        path = root / MARKER_PATH; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'{"damaged":"interrupted writer"}')
    before = inventory(root); calls = []
    authority = PublicationAuthority('adapter-test-denied', '1', lambda request: calls.append(request) or False)
    with pytest.raises((ModelError, OperationFailure)) as error:
        run(authority)
    code = int(error.value.kind) if isinstance(error.value, OperationFailure) else error.value.exit_code
    assert code == (7 if state == 'denied' else 5)
    if state == 'blocked': assert calls == []
    else: assert calls
    assert inventory(root) == before


@pytest.mark.parametrize('words', [
    ('query',), ('show', 'SR-REQ-' + '0' * 26), ('why', 'SR-REQ-' + '0' * 26),
    ('proposal', 'review', 'start', 'SR-PROP-' + '0' * 26,
     '--expected-revision', '1', '--actor-type', 'human', '--actor-id', 'test-author'),
    ('proposal', 'apply', 'SR-PROP-' + '0' * 26,
     '--expected-revision', '3', '--actor-type', 'human', '--actor-id', 'test-author'),
    ('proposal', 'apply', 'SR-PROP-' + '0' * 26,
     '--expected-revision', '3', '--actor-type', 'human', '--actor-id', 'test-author', '--dry-run'),
])
def test_real_cli_commands_block_before_entering_the_normal_handler(tmp_path, words):
    from support.model import configuration_file
    from specroad.cli.application import dispatch_result
    configuration_file(tmp_path)
    path = tmp_path / MARKER_PATH; path.parent.mkdir(parents=True); path.write_bytes(b'{}')
    before = inventory(tmp_path)
    with no_write_attempts():
        result = dispatch_result([*words, '--project', str(tmp_path)])
    assert result.exit_code == 5
    facts = result.details['preflight']
    assert facts['project_corrupted'] and facts['manual_git_restore_required']
    assert not facts['normal_operation_started'] and inventory(tmp_path) == before
