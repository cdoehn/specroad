"""Release-Baseline boundary cases using native decisions and real publication.

Human approvals below are explicit synthetic host fixtures. They do not claim
production approval, external CI execution or a full-suite result.
"""
from copy import deepcopy
from dataclasses import replace

import pytest

from specroad.archive import assess_release_baseline_readiness, ReleaseBaselineSelectionConflict
from specroad.archive.objects import SnapshotObject
from specroad.archive.verification import verify_baseline_objects, verify_baseline_snapshot
from specroad.changes import ChangePlan, TargetModel, PublicationAuthority
from specroad.changes.baselines import prepare_baseline_operation, object_documents
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.model_manifest import ProjectReadBinding
from specroad.model.paths import artifact_path
from specroad.planning import ReleaseReadinessContext, assess_release_readiness
from specroad.security import ProjectBoundary
from specroad.storage.json_syntax import parse_json_object
from specroad.validation import ReviewVerifier, ReviewVerification
from specroad.verification import VerificationEvaluation
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.records import ref, record_value
from test_artifact_creation import ACTOR
from test_release_baseline import prepare, publish
from test_release_readiness import (release_case as shared_release_case, context, native_bindings, services,
    RELEASE, NOW, POLICY, INPUTS, gates as gate_rows)
from test_release_readiness_right import blocker_case, passive, trusted, refresh_reviews


def release_case():
    # Own nested shared scope/policy fixtures before a negative case changes them.
    values, evaluation = shared_release_case()
    return deepcopy(values), evaluation


def reasons(report):
    return {row['gate_id']: row['findings'] for row in report.data['gates'] if row['findings']}


def release_project(root, *, values=None, evaluation=None, configuration_id=None):
    """Own a real project root while retaining native scope/verification inputs."""
    if values is None:
        values, _ = release_case()
    original = context(values, evaluation=evaluation, configuration_id=configuration_id)._model
    root.mkdir(); info = root.stat()
    model = TargetModel(original.configuration_bytes,
        ProjectReadBinding(original.binding.project_id, str(root), (info.st_dev, info.st_ino)),
        original.documents, profile=original.profile, resource_files=original.resource_files)
    for path, raw in model.source_files.items():
        put(root, path, raw)
    (root / '.specroad/locks').mkdir(parents=True)
    ctx = ReleaseReadinessContext(model, RELEASE, scope_bindings=native_bindings(model),
        evaluated_at=NOW, configuration_id=configuration_id, evaluation=evaluation,
        inputs=dict(INPUTS), input_roles={p: 'input' for p in INPUTS})
    return model, ctx


@pytest.mark.parametrize('legacy', [False, True])
@pytest.mark.parametrize('stored_reversed', [False, True])
def test_normalized_identical_selection_keeps_original_stored_bytes(tmp_path, legacy, stored_reversed):
    values, selected = release_case(); stored = selected.data
    if stored_reversed:
        stored['required_runs'].reverse()
    values[0]['readiness_policy']['verification_evaluation'] = stored
    if legacy:
        del values[0]['readiness_policy']['format_version']
    values = refresh_reviews(values)
    external = deepcopy(stored); external['required_runs'].reverse()
    assert external != stored
    assert VerificationEvaluation(canonical_json_bytes(external)).sha256 == selected.sha256
    model, ctx = release_project(tmp_path / 'project', values=values)
    provided = services(ctx); before = inventory(tmp_path)
    with no_write_attempts():
        first = assess_release_baseline_readiness(model, release_id=RELEASE,
            readiness_context=ctx, gates=provided)
        repeated = assess_release_baseline_readiness(model, release_id=RELEASE, evaluation=external,
            readiness_context=ctx, gates=provided)
        assert first.data == repeated.data
        assert repeated.data['stored_evaluation'] == stored
        assert repeated.data['stored_evaluation_sha256'] == canonical_json_sha256(stored)
        if legacy:
            with pytest.raises(ModelError) as error:
                prepare(model, ctx, gates=provided, evaluation=external)
            assert error.value.reason == 'release_baseline_readiness_required'
        else:
            assert repeated.data['ready'], repeated.data['blockers']
            preview = prepare(model, ctx, gates=provided, evaluation=external)
            assert preview['target_validated'], preview['diagnostics']
            assert preview['plan']['operations'][0]['record']['verification_evaluation'] == stored
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('legacy', [False, True])
@pytest.mark.parametrize('field', ['run', 'identity', 'incomplete'])
def test_different_selection_stays_code_six_before_any_admission(tmp_path, legacy, field):
    values, selected = release_case()
    if legacy:
        del values[0]['readiness_policy']['format_version']
    model, ctx = release_project(tmp_path / 'project', values=values)
    external = selected.data
    if field == 'run': external['required_runs'][0]['run_ids'] = ['ci:another']
    elif field == 'identity': external['evaluation_id'] = 'EVAL-' + '0' * 25 + '2'
    else: external = {}
    calls = []
    provided = [replace(g, check=lambda c: calls.append(c) or c.result()) for g in services(ctx)]
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ReleaseBaselineSelectionConflict) as error:
        prepare(model, ctx, evaluation=external, gates=provided)
    assert error.value.exit_code == 6
    assert error.value.pointer == '/readiness_policy/verification_evaluation'
    assert not calls and inventory(tmp_path) == before


@pytest.mark.parametrize('policy', [POLICY, {}, {'old_allow': True}])
def test_external_selection_is_only_provisional_and_never_a_baseline(tmp_path, policy):
    values, selected = release_case(); values[0]['readiness_policy'] = deepcopy(policy)
    values = refresh_reviews(values)
    model, ctx = release_project(tmp_path / 'project', values=values, evaluation=selected)
    provided = services(ctx); before = inventory(tmp_path)
    with no_write_attempts():
        native = assess_release_readiness(ctx, gates=provided)
        assert native.data['provisional']
        assert native.data['ready'] is ('format_version' in policy), reasons(native)
        observed = assess_release_baseline_readiness(model, release_id=RELEASE,
            readiness_context=ctx, gates=provided)
        assert not observed.data['ready']
        with pytest.raises(ModelError): observed.require_ready()
        for external in (None, selected.data):
            with pytest.raises(ModelError): prepare(model, ctx, gates=provided, evaluation=external)
        with pytest.raises(ModelError):
            prepare_baseline_operation(model, baseline_id=ref('BASE'), name='Refused',
                actor=ACTOR, planned_at=NOW, release_id=RELEASE)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('gate', ['scope', 'approval', 'implementation', 'verification',
                                 'coverage', 'risks', 'issues', 'relations'])
def test_every_native_gate_can_block_baseline_preparation(tmp_path, gate):
    values, _ = release_case()
    if gate in ('risks', 'issues'):
        values, _ = blocker_case('risk' if gate == 'risks' else 'issue', 'open')
    elif gate == 'scope': values[0]['scope_descriptor']['boundary_policy'] = 'partial'
    elif gate == 'approval': next(v for v in values if v['artifact_type'] == 'decision')['maturity'] = 'draft'
    elif gate == 'implementation': next(v for v in values if v['artifact_type'] == 'capability')['implementation_status'] = 'not_started'
    elif gate == 'verification': next(v for v in values if v['artifact_type'] == 'evidence')['result'] = 'failed'
    elif gate == 'coverage': next(v for v in values if v['artifact_type'] == 'evidence')['run_context']['run_id'] = 'ci:other'
    else:
        values = [v for v in values if v['artifact_type'] != 'relation_review']
    model, ctx = release_project(tmp_path / 'project', values=values)
    provided = services(ctx); before = inventory(tmp_path)
    with no_write_attempts():
        result = assess_release_readiness(ctx, gates=provided)
        assert gate_rows(result)[gate]['status'] in ('failed', 'incomplete')
        with pytest.raises(ModelError) as error: prepare(model, ctx, gates=provided)
    assert error.value.reason == 'release_baseline_readiness_required'
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('case', ['missing', 'unavailable', 'unbound', 'untyped', 'revoked',
                                 'unauthenticated', 'wrong_subject', 'future', 'error'])
def test_unbound_or_unconfirmed_blocker_completion_never_seals_a_baseline(tmp_path, case):
    values, decision = blocker_case(); review = passive(decision); verifier = trusted()
    if case == 'unavailable': verifier = None
    elif case == 'revoked': verifier = trusted(current=False)
    elif case == 'unauthenticated': verifier = trusted(human=False)
    elif case == 'wrong_subject': review = passive(decision, subject_id=ref('RISK', '2'))
    elif case == 'future': review = passive(decision, reviewed_at='2026-10-23T00:00:00Z')
    elif case in ('unbound', 'untyped', 'error'):
        def check(c, r):
            if case == 'error': raise RuntimeError('private-host-detail')
            if case == 'untyped': return True
            return ReviewVerification('0' * 64, r.sha256, True, True)
        verifier = ReviewVerifier('synthetic-refusal', '1', check)
    model, ctx = release_project(tmp_path / 'project', values=values)
    provided = services(ctx); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        prepare(model, ctx, gates=provided, blocker_reviews=[] if case == 'missing' else [review],
            blocker_verifier=verifier)
    assert error.value.reason == 'release_baseline_readiness_required'
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('kind,status', [('risk', 'accepted'), ('risk', 'closed'), ('issue', 'resolved')])
def test_confirmed_blocker_completion_allows_real_sealed_publication(tmp_path, kind, status):
    values, decision = blocker_case(kind, status)
    model, ctx = release_project(tmp_path / 'project', values=values)
    provided = services(ctx); options = dict(blocker_reviews=[passive(decision)], blocker_verifier=trusted())
    preview = prepare(model, ctx, gates=provided, **options)
    assert preview['target_validated'], preview['diagnostics']
    plan = ChangePlan(canonical_json_bytes(preview['plan']))
    result = publish(plan, model, ctx, gates=provided, **options)
    assert result['write_state'] == 'committed'
    record = plan.data['operations'][0]['record']; root = tmp_path / 'project'
    raw = (root / artifact_path('baseline', record['id'], 'SR')).read_bytes()
    assert raw == canonical_json_bytes(record) and record['baseline_state'] == 'sealed'
    with no_write_attempts(): checked = verify_baseline_snapshot(ProjectBoundary(root), raw)
    assert checked['snapshot_integrity_verified'] and not checked['release_authorized']
    for path, content in model.source_files.items(): assert (root / path).read_bytes() == content


def test_old_completion_observation_cannot_authorize_a_saved_plan_at_a_new_time(tmp_path):
    values, decision = blocker_case(); review = passive(decision); observed = []
    def check(c, r):
        result = ReviewVerification(c.input_sha256, r.sha256, True, True)
        observed.append(result); return result
    verifier = ReviewVerifier('synthetic-bound-observation', '1', check)
    root = tmp_path / 'project'; model, ctx = release_project(root, values=values)
    native = assess_release_readiness(ctx, gates=services(ctx), blocker_reviews=[review], blocker_verifier=verifier)
    assert native.data['ready'], reasons(native)
    preview = prepare(model, ctx, blocker_reviews=[review], blocker_verifier=verifier)
    assert preview['target_validated'] and observed
    other = ReleaseReadinessContext(model, RELEASE, scope_bindings=native_bindings(model),
        evaluated_at='2026-10-22T01:00:00Z', inputs=dict(INPUTS), input_roles={p: 'input' for p in INPUTS})
    replay = replace(verifier, check=lambda c, r: observed[-1])
    calls = []
    with pytest.raises(ModelError):
        publish(ChangePlan(canonical_json_bytes(preview['plan'])), model, other,
            blocker_reviews=[review], blocker_verifier=replay,
            authority=PublicationAuthority('observe-authority', '1', lambda req: calls.append(req) or True))
    assert not calls and not (root / 'spec/baselines').exists() and not (root / 'archive').exists()


@pytest.mark.parametrize('changed', ['selection', 'normalized_hash', 'stored_hash', 'scope', 'release'])
def test_archive_rejects_self_consistently_rehashed_but_false_selection_metadata(tmp_path, changed):
    model, _ = release_project(tmp_path / 'project')
    operation = prepare_baseline_operation(model, baseline_id=ref('BASE'), name='Inert snapshot',
        actor=ACTOR, planned_at=NOW, release_id=RELEASE)
    record = operation['record']; documents = object_documents(operation)
    objects = {d.path: SnapshotObject(d.content) for d in documents}
    row = next(r for r in record['manifest'] if r['role'] == 'release_selection')
    value = parse_json_object(objects.pop(row['object_path']).content)
    if changed == 'selection': value['verification_evaluation']['evaluation_id'] = 'EVAL-' + '0' * 25 + '2'
    elif changed == 'normalized_hash': value['evaluation_sha256'] = '0' * 64
    elif changed == 'stored_hash': value['stored_evaluation_sha256'] = '0' * 64
    elif changed == 'scope': value['scope_descriptor']['configuration_id'] = ref('CFG')
    else: value['release_id'] = ref('REL', '1')
    item = SnapshotObject(canonical_json_bytes(value)); objects[item.reference.path] = item
    row.update(object_path=item.reference.path, sha256=item.reference.sha256, size=item.reference.size)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        verify_baseline_objects(canonical_json_bytes(record), tuple(objects.values()))
    assert error.value.reason == 'release_baseline_selection_binding_mismatch'
    assert inventory(tmp_path) == before


def test_publication_retains_original_stored_order_beside_normalized_selection_hash(tmp_path):
    values, evaluation = release_case()
    stored = evaluation.data
    stored['required_runs'].reverse()
    values[0]['readiness_policy']['verification_evaluation'] = stored
    values = refresh_reviews(values)
    model, ctx = release_project(tmp_path / 'project', values=values)
    provided = services(ctx)
    external = VerificationEvaluation(canonical_json_bytes(stored))
    native = assess_release_readiness(ctx, gates=provided)
    assert native.data['ready'], reasons(native)
    preview = prepare(model, ctx, gates=provided, evaluation=external.data)
    assert preview['target_validated'], preview['diagnostics']
    plan = ChangePlan(canonical_json_bytes(preview['plan']))
    result = publish(plan, model, ctx, gates=provided)
    assert result['write_state'] == 'committed'
    record = plan.data['operations'][0]['record']; root = tmp_path / 'project'
    assert record['verification_evaluation'] == stored != external.data
    selection_row = next(r for r in record['manifest'] if r['role'] == 'release_selection')
    selection = parse_json_object((root / selection_row['object_path']).read_bytes())
    assert selection['verification_evaluation'] == stored
    assert selection['stored_evaluation_sha256'] == canonical_json_sha256(stored)
    assert selection['evaluation_sha256'] == external.sha256
    assert selection['scope_descriptor'] == ctx.data['binding']['scope_descriptor']
    with no_write_attempts():
        checked = verify_baseline_snapshot(ProjectBoundary(root), canonical_json_bytes(record))
    assert checked['snapshot_integrity_verified'] and not checked['release_authorized']
    for path, raw in model.source_files.items(): assert (root / path).read_bytes() == raw


def test_a_different_baseline_configuration_cannot_borrow_unconfigured_readiness(tmp_path):
    values, _ = release_case()
    parent = record_value('configuration', id=ref('CFG', '1'), name='Parent')
    child = record_value('configuration', name='Child', parent=parent['id'], dimensions=[])
    values.extend([parent, child])
    root = tmp_path / 'project'; model, ctx = release_project(root, values=values)
    # Check the actual selected parent chain with the existing native service;
    # no configuration success callback substitutes for it. The readiness scope
    # remains unconfigured, so this does not authorize a configured snapshot.
    from specroad.configurations._gate_context import _ConfigurationGateContext
    from specroad.configurations.gates import _bound_configuration_gate
    from specroad.graph.relations import SourceRelations
    binding = _ConfigurationGateContext(
        tuple(SourceRelations(d.content, path=d.path) for d in model.documents), child['id'])
    provided = [*services(ctx), _bound_configuration_gate(binding)]
    before = inventory(root)
    with no_write_attempts():
        native = assess_release_readiness(ctx, gates=provided)
        assert native.data['ready'], reasons(native)
        with pytest.raises(ModelError) as error:
            prepare(model, ctx, gates=provided, configuration_id=child['id'])
    assert error.value.reason == 'release_baseline_readiness_binding_mismatch'
    assert inventory(root) == before
    assert not (root / 'spec/baselines').exists() and not (root / 'archive').exists()
