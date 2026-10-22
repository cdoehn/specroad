"""Native Release admission, stored bytes and real sealed publication.

Trusted approval/review services are explicit synthetic fixtures, not claims of
real human approval or CI execution. Scope, verification and writer are native.
"""
from copy import deepcopy
from hashlib import sha256

import pytest

from specroad.archive import assess_release_baseline_readiness
from specroad.archive.creation import prepare_baseline_creation, create_baseline
from specroad.archive.verification import verify_baseline_snapshot
from specroad.authoring.execution import apply_authoring_plan
from specroad.changes import ChangePlan, PublicationAuthority, TargetModel
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.model.model_manifest import ProjectReadBinding
from specroad.model.paths import artifact_path
from specroad.planning import ReleaseReadinessContext
from specroad.security import ProjectBoundary
from specroad.validation import ModelGate, ReviewVerifier, ReviewVerification
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.records import ref
from test_artifact_creation import ACTOR, ALLOW
from test_release_readiness import (release_case, context, native_bindings,
    services, RELEASE, NOW, INPUTS)


def release_project(root, *, mutate=None):
    values, evaluation = release_case()
    if mutate is not None:
        mutate(values)
    original = context(values)._model
    root.mkdir()
    info = root.stat()
    model = TargetModel(original.configuration_bytes,
        ProjectReadBinding(original.binding.project_id, str(root), (info.st_dev, info.st_ino)),
        original.documents, profile=original.profile, resource_files=original.resource_files)
    for path, raw in model.source_files.items():
        put(root, path, raw)
    (root / '.specroad/locks').mkdir(parents=True)
    current = ReleaseReadinessContext(model, RELEASE, scope_bindings=native_bindings(model),
        evaluated_at=NOW, inputs=dict(INPUTS), input_roles={p: 'input' for p in INPUTS})
    return model, current, evaluation


def prepare(model, ctx, *, gates=None, **changes):
    fields = dict(baseline_kind='release', baseline_id=ref('BASE'), name='Release snapshot',
        actor=ACTOR, planned_at=NOW, change_plan_id='CP-release', request_id='release-1',
        release_id=RELEASE, readiness_context=ctx,
        gates=services(ctx) if gates is None else gates)
    fields.update(changes)
    return prepare_baseline_creation(model, **fields)


def publish(plan, model, ctx, *, gates=None, **changes):
    fields = dict(transaction_id='txn-release', authority=ALLOW,
        readiness_context=ctx, gates=services(ctx) if gates is None else gates)
    fields.update(changes)
    return create_baseline(plan, model, **fields)


@pytest.mark.parametrize('repeat', [False, True])
def test_stored_complete_selection_and_all_eight_gates_prepare_the_same_native_plan(tmp_path, repeat):
    model, ctx, evaluation = release_project(tmp_path / 'project')
    before = inventory(tmp_path)
    with no_write_attempts():
        preview = prepare(model, ctx, evaluation=deepcopy(evaluation.data) if repeat else None)
        repeated = prepare(model, ctx)
        observed = assess_release_baseline_readiness(model, release_id=RELEASE,
            readiness_context=ctx, gates=services(ctx))
        fresh = observed.require_ready()
    assert preview == repeated and preview['target_validated']
    assert preview['write_state'] == 'not_committed' and inventory(tmp_path) == before
    assert fresh.data['ready'] and not fresh.data['provisional']
    assert len(fresh.data['gates']) == 8
    assert observed.data['readiness_evaluated'] and not observed.data['write_authorized']
    record = preview['plan']['operations'][0]['record']
    assert record['baseline_kind'] == 'release' and record['verification_evaluation'] == evaluation.data


def test_native_release_publication_binds_selection_scope_and_objects_without_changing_sources(tmp_path):
    root = tmp_path / 'project'; model, ctx, evaluation = release_project(root)
    preview = prepare(model, ctx)
    assert preview['target_validated'], preview['diagnostics']
    plan = ChangePlan(canonical_json_bytes(preview['plan']))
    result = publish(plan, model, ctx)
    assert result['write_state'] == 'committed' and result['completion']['current_target_verified']
    record = plan.data['operations'][0]['record']
    raw = (root / artifact_path('baseline', record['id'], 'SR')).read_bytes()
    assert raw == canonical_json_bytes(record)
    assert record['baseline_state'] == 'sealed' and record['maturity'] == 'approved'
    assert record['scope_descriptor']['scope_kind'] == 'project'
    for path, content in model.source_files.items():
        assert (root / path).read_bytes() == content
    row, = [r for r in record['manifest'] if r['role'] == 'release_selection']
    selected_raw = (root / row['object_path']).read_bytes()
    assert sha256(selected_raw).hexdigest() == row['sha256'] and len(selected_raw) == row['size']
    from specroad.storage.json_syntax import parse_json_object
    selected = parse_json_object(selected_raw)
    assert selected['verification_evaluation'] == evaluation.data
    assert selected['evaluation_sha256'] == evaluation.sha256
    assert selected['scope_descriptor'] == ctx.data['binding']['scope_descriptor']
    assert selected['release_id'] == RELEASE
    # Independent archive verification does not claim a historical approval.
    with no_write_attempts():
        checked = verify_baseline_snapshot(ProjectBoundary(root), raw)
    assert checked['snapshot_integrity_verified'] and not checked['release_authorized']
    before = inventory(root)
    # Native durable replay reports the original publication, without requiring
    # present-day approval of that immutable historical snapshot again.
    with no_write_attempts():
        replay = create_baseline(plan, model, transaction_id='txn-replayed', authority=ALLOW)
    assert replay['replayed'] and replay['completion']['transaction_id'] == 'txn-release'
    assert inventory(root) == before


@pytest.mark.parametrize('missing', ['lifecycle', 'evidence_currentness', 'review_currentness', 'task_done'])
def test_a_missing_mandatory_native_provider_keeps_release_preparation_read_only(tmp_path, missing):
    model, ctx, _ = release_project(tmp_path / 'project'); before = inventory(tmp_path)
    provided = [g for g in services(ctx) if g.gate_id != missing]
    with no_write_attempts(), pytest.raises(ModelError) as error:
        prepare(model, ctx, gates=provided)
    assert error.value.reason == 'release_baseline_readiness_required'
    assert inventory(tmp_path) == before


def test_failed_current_evidence_blocks_a_stored_success_selection(tmp_path):
    def mutate(values):
        next(v for v in values if v['artifact_type'] == 'evidence')['result'] = 'failed'
    model, ctx, _ = release_project(tmp_path / 'project', mutate=mutate)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        prepare(model, ctx)
    assert error.value.reason == 'release_baseline_readiness_required'
    assert inventory(tmp_path) == before


def test_revoked_human_done_review_cannot_reuse_a_successful_preview(tmp_path):
    current = [True]
    verifier = ReviewVerifier('revocable-host', '1', lambda ctx, review:
        ReviewVerification(ctx.input_sha256, review.sha256, True, current[0]))
    model, ctx, _ = release_project(tmp_path / 'project')
    provided = services(ctx, done_verifier=verifier)
    preview = prepare(model, ctx, gates=provided)
    assert preview['target_validated']
    plan = ChangePlan(canonical_json_bytes(preview['plan']))
    current[0] = False; before = inventory(tmp_path)
    with pytest.raises(ModelError) as error:
        publish(plan, model, ctx, gates=provided)
    assert error.value.reason == 'complete_target_validation_required'
    assert tuple(row for row in inventory(tmp_path) if '/.specroad/' not in row[0]) == tuple(
        row for row in before if '/.specroad/' not in row[0])
    assert not (tmp_path / 'project/.specroad/transactions').exists()


@pytest.mark.parametrize('forged_gate', [False, True])
def test_saved_release_plan_requires_the_native_gate_before_generic_publication(tmp_path, forged_gate):
    model, ctx, _ = release_project(tmp_path / 'project')
    preview = prepare(model, ctx); plan = ChangePlan(canonical_json_bytes(preview['plan']))
    calls = []; provided = services(ctx)
    if forged_gate:
        provided.append(ModelGate('extension:release-baseline', 'fake-success',
            lambda target: target.dependency_result({key: [] for key in target.subjects}),
            lambda target: target.result()))
    before = inventory(tmp_path)
    with pytest.raises(ModelError) as error:
        apply_authoring_plan(plan, model, command_id='baseline.create', transaction_id='txn-forged',
            authority=PublicationAuthority('observe', '1', lambda req: calls.append(req) or True),
            gates=provided)
    assert error.value.reason == 'release_baseline_readiness_required'
    assert not calls
    # A lock may be acquired by the normal writer, never normative publication.
    assert tuple(row for row in inventory(tmp_path) if '/.specroad/' not in row[0]) == tuple(
        row for row in before if '/.specroad/' not in row[0])


def test_readiness_context_from_a_different_model_cannot_open_the_baseline(tmp_path):
    model, _, _ = release_project(tmp_path / 'project')
    _, other, _ = release_project(tmp_path / 'other')
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        prepare(model, other)
    assert error.value.reason == 'release_baseline_readiness_binding_mismatch'
    assert inventory(tmp_path) == before


def test_current_live_source_change_blocks_real_release_publication(tmp_path):
    root = tmp_path / 'project'; model, ctx, _ = release_project(root)
    preview = prepare(model, ctx); plan = ChangePlan(canonical_json_bytes(preview['plan']))
    document = model.documents[0]; put(root, document.path, document.content + b' ')
    with pytest.raises(ModelError):
        publish(plan, model, ctx)
    assert not (root / 'spec/baselines').exists() and not (root / 'archive').exists()
    assert (root / document.path).read_bytes() == document.content + b' '


def test_native_readiness_is_rechecked_during_publication_after_host_revocation(tmp_path):
    current = [True]
    verifier = ReviewVerifier('boundary-host', '1', lambda ctx, review:
        ReviewVerification(ctx.input_sha256, review.sha256, True, current[0]))
    root = tmp_path / 'project'; model, ctx, _ = release_project(root)
    provided = services(ctx, done_verifier=verifier)
    preview = prepare(model, ctx, gates=provided)
    assert preview['target_validated']
    plan = ChangePlan(canonical_json_bytes(preview['plan']))
    called = []
    def revoke(request):
        called.append(request); current[0] = False
        return True
    with pytest.raises(ModelError):
        publish(plan, model, ctx, gates=provided,
            authority=PublicationAuthority('explicit-host', '1', revoke))
    assert called and not (root / 'spec/baselines').exists() and not (root / 'archive').exists()
    for path, content in model.source_files.items():
        assert (root / path).read_bytes() == content
