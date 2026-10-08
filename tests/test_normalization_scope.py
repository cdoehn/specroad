"""Complete format selection, protected originals and exact byte/value contracts."""
from hashlib import sha256
from pathlib import Path
import json
import pytest
from specroad.changes import (TargetModel, prepare_format_target, prepare_change_target,
    assess_change_target, dry_run_change, prepare_publication_check,
    PublicationCheckError, ChangePlanError, apply_change_plan)
from specroad.model.canonical import canonical_object_sha256, canonical_json_bytes
from specroad.model.paths import artifact_path
from specroad.validation import ModelDocument
from support.normalization import FIELDS, operation
from support.normalization_scope import prepared, GATES
from support.targets import model, POLICY, gate
from support.records import record_value
from support.read_only import no_write_attempts, inventory
from support.publication import files, NativeGuardStorage


def test_complete_scope_has_exact_bytehashes_and_preserves_every_value(tmp_path):
    m, p, c = prepared(tmp_path)
    result = assess_change_target(p, m, policy=POLICY, gates=GATES)
    assert result.target_validated
    assert {op['path'] for op in p.data['operations']} == set(m.source_files)
    assert {d.path for d in result.documents} == {d.path for d in m.documents}
    assert {d.path for d in result.resource_documents} == set(m.source_files) - {d.path for d in m.documents}
    assert result.data['base_manifest'] == result.data['target_manifest']
    for document in result.publication_documents:
        before = m.source_files[document.path]
        assert before != document.content
        assert json.loads(before) == json.loads(document.content)
        assert canonical_object_sha256(before) == canonical_object_sha256(document.content)
        op = next(op for op in p.data['operations'] if op['path'] == document.path)
        assert op['expected_byte_sha256'] == sha256(before).hexdigest()
        assert op['target_byte_sha256'] == sha256(document.content).hexdigest()
    assert files(tmp_path) == m.source_files and not (tmp_path / '.specroad').exists()


@pytest.mark.parametrize('path', ['specroad.json', 'profiles/core.json', 'rules/sample.json', 'mappings/sample.json'])
def test_explicit_single_resource_plan_uses_the_same_target_path(tmp_path, path):
    m, p, _ = prepared(tmp_path, select=[path])
    direct = prepare_change_target(m, p.data['operations'], policy=POLICY, gates=GATES, **FIELDS)
    assert direct.plan.source_bytes == p.source_bytes and direct.target_validated
    c = prepare_publication_check(p, m, policy=POLICY, gates=GATES)
    assert c.request.data['changed_paths'] == [path]
    assert direct.artifacts == m.artifacts


def test_complete_format_check_never_creates_project_or_operational_files(tmp_path):
    m, p, _ = prepared(tmp_path)
    before = inventory(tmp_path)
    with no_write_attempts():
        assessment = prepare_format_target(m, policy=POLICY, gates=GATES, **FIELDS)
        result = dry_run_change(assessment.plan, m, policy=POLICY, gates=GATES, fail_on_change=True)
    assert assessment.plan.source_bytes == p.source_bytes
    assert result.data['would_change'] and result.data['exit_code'] == 1
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('status,maturity', [('draft','draft'), ('validated','proposed'),
    ('checked','proposed'), ('in_review','in_review'), ('approved','approved')])
def test_active_proposals_preserve_control_and_content_metadata(status, maturity):
    value = record_value('proposal', proposal_status=status, maturity=maturity)
    m = model([value])
    result = prepare_format_target(m, policy=POLICY, gates=(gate('lifecycle'),), **FIELDS)
    assert result.target_validated
    assert result.artifacts == [value]
    assert artifact_path('proposal', value['id'], 'SR') in result.data['representation']['changed_paths']
    assert result.data['lifecycle']['metadata_applied'] is False


@pytest.mark.parametrize('kind,status,maturity', [('evidence',None,None), ('baseline',None,None),
    ('relation_review',None,None), ('proposal','applied','approved'),
    ('proposal','rejected','rejected'), ('proposal','stale','retired')])
def test_protected_records_are_excluded_and_explicit_operations_refused(kind, status, maturity):
    overrides = {} if status is None else {'proposal_status': status, 'maturity': maturity}
    value = record_value(kind, **overrides)
    m = model([value])
    with no_write_attempts():
        result = prepare_format_target(m, policy=POLICY, **FIELDS)
        with pytest.raises(ChangePlanError):
            prepare_change_target(m, [operation(m.documents[0])], policy=POLICY, **FIELDS)
    path = m.documents[0].path
    assert path not in {op['path'] for op in result.plan.data['operations']}
    assert next(d for d in result.documents if d.path == path).content == m.documents[0].content
    assert not result.target_validated  # No fabricated lifecycle/currentness services.


def test_resources_require_the_real_registered_whole_target_service(tmp_path):
    m, p, _ = prepared(tmp_path)
    missing = assess_change_target(p, m, policy=POLICY)
    denied = assess_change_target(p, m, policy=POLICY, gates=(gate('extension:target-resources',
        check=lambda ctx: ctx.result([{'reason':'resource_denied','severity':'error'}])),))
    assert not missing.target_validated and not denied.target_validated
    for gates in ((), (gate('extension:target-resources', check=lambda ctx:
                           ctx.result([{'reason':'resource_denied','severity':'error'}])),)):
        with no_write_attempts(), pytest.raises(PublicationCheckError):
            prepare_publication_check(p, m, policy=POLICY, gates=gates)


@pytest.mark.parametrize('path', ['archive/note.json', 'attachments/unreferenced.json',
    'generated/output.json', '.specroad/cache/local.json', 'notes.json'])
def test_nonformat_resources_remain_byte_exact_and_are_not_scanned_as_model(tmp_path, path):
    m, p, _ = prepared(tmp_path)
    file = tmp_path / path
    file.parent.mkdir(parents=True, exist_ok=True)
    raw = b'original non-model bytes\n'
    file.write_bytes(raw)
    with no_write_attempts():
        same = prepare_format_target(m, policy=POLICY, gates=GATES, **FIELDS)
        check = prepare_publication_check(same.plan, m, policy=POLICY, gates=GATES)
    assert same.plan.source_bytes == p.source_bytes
    assert path not in check.request.data['changed_paths'] and file.read_bytes() == raw


def test_execution_readback_accepts_only_the_exact_changed_resource_binding(tmp_path):
    m, p, check = prepared(tmp_path)
    class Storage(NativeGuardStorage):
        def publish(self, request):
            # NativeGuardStorage is only a test backend. The separately tested
            # real writer performs the durable checks; this checks orchestration.
            from specroad.changes import PublicationReceipt
            self.calls.append(request.sha256)
            for d in request.documents: (self.root / d.path).write_bytes(d.content)
            v = request.data
            return PublicationReceipt(request.sha256, v['target_root_sha256'], v['request_id'],
                                      tuple(v['changed_paths']), 'format-test')
    store = Storage(m, check)
    result = apply_change_plan(p, m, policy=POLICY, gates=GATES, backend=store.backend)
    assert result.data['write_state'] == 'committed' and result.data['would_change']
    assert store.model.artifacts == m.artifacts
    assert store.model.resources_sha256 != m.resources_sha256
    assert files(tmp_path) == {**m.source_files, **{d.path:d.content for d in check.request.documents}}
