"""Explicit migration uses the native guarded writer and preserves old inputs."""
import json

import pytest

from specroad.authoring.update import update_artifact
from specroad.changes import (ChangeOperation, ChangePlanError, PublicationAuthority,
    PublicationCheckError, TargetError, TargetModel)
from specroad.changes.json_patch import JsonPatch
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.planning import prepare_readiness_policy_update, prepare_readiness_status_update
from specroad.storage.domain_artifact import DomainArtifact
from specroad.storage.record_artifact import RecordArtifact
from specroad.validation import ModelDocument, ModelGate
from support.domain import domain_value
from support.records import record_value
from support.read_only import inventory, no_write_attempts
from test_artifact_creation import project
from test_artifact_update import arguments, ACTOR, TIME
from test_release_readiness import POLICY


def stored(root, kind, *, maturity='draft'):
    model, _ = project(root, 'verification')
    if kind == 'release': value = domain_value(kind, readiness_policy={'old_allow': True})
    elif kind == 'risk': value = domain_value(kind, risk_status='LegacyAccepted')
    else: value = record_value(kind, issue_status='LegacyDone', resolution_criteria='Investigate')
    value['maturity'] = maturity
    previous = next(d for d in model.documents if json.loads(d.content)['artifact_type'] == 'requirement')
    path = artifact_path(kind, value['id'], 'SR'); raw = canonical_json_bytes(value)
    documents = [ModelDocument(path, raw) if d.path == previous.path else d for d in model.documents]
    (root / previous.path).unlink()
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    (root / path).write_bytes(raw); (root / path).chmod(0o640)
    model = TargetModel(model.configuration_bytes, model.binding, documents,
        profile=model.profile, resource_files=model.resource_files)
    parser = RecordArtifact if kind == 'issue' else DomainArtifact
    return model, parser(raw, path=path)


def operation(subject, selected=None):
    if subject.data['artifact_type'] == 'release':
        return prepare_readiness_policy_update(subject, POLICY if selected is None else selected)
    return prepare_readiness_status_update(subject, 'closed' if selected is None else selected)


@pytest.mark.parametrize('kind', ['release', 'risk', 'issue'])
def test_explicit_migration_publishes_one_native_revision_and_no_review_or_approval(tmp_path, kind):
    root = tmp_path / 'project'; supplied, subject = stored(root, kind)
    before = inventory(root); raw = subject.source_bytes
    with no_write_attempts(): op = operation(subject)
    assert subject.source_bytes == raw and inventory(root) == before
    assert op.data['expected_revision'] == subject.data['revision']
    assert op.data['expected_sha256'] == canonical_json_sha256(subject.data)
    result = update_artifact(supplied, op, **arguments(root))
    expected = JsonPatch(op.data['patch']).apply(subject.data).data
    expected.update(revision=2, updated_by=ACTOR, updated_at=TIME)
    actual = type(subject)((root / subject.path).read_bytes(), path=subject.path)
    assert actual.data == expected and actual.data['maturity'] == 'draft'
    assert result['completion']['commit_completed'] and result['completion']['cleanup_completed']
    assert (root / subject.path).stat().st_mode & 0o777 == 0o640
    assert not any(k in actual.data for k in ('readiness', 'ready', 'review_verified'))
    if kind == 'release': assert actual.data['readiness_policy']['blocker_decisions'] == []
    after = {name: rest for name, *rest in inventory(root)}
    for name, *rest in before:
        if name != subject.path: assert after[name] == rest
    assert subject.source_bytes == raw


@pytest.mark.parametrize('kind', ['release', 'risk', 'issue'])
@pytest.mark.parametrize('guard', ['revision', 'hash'])
def test_migration_cannot_relax_expected_original_basis(tmp_path, kind, guard):
    root = tmp_path / 'project'; supplied, subject = stored(root, kind)
    data = operation(subject).data
    data['expected_revision' if guard == 'revision' else 'expected_sha256'] = 99 if guard == 'revision' else '0' * 64
    before = inventory(root)
    with pytest.raises(ChangePlanError) as caught:
        update_artifact(supplied, ChangeOperation(data), **arguments(root))
    assert caught.value.reason == ('expected_revision_mismatch' if guard == 'revision' else 'expected_hash_mismatch')
    assert inventory(root) == before


@pytest.mark.parametrize('barrier', ['authority', 'physical_base', 'lifecycle'])
def test_migration_retains_publication_and_validation_barriers(tmp_path, barrier):
    root = tmp_path / 'project'
    supplied, subject = stored(root, 'release', maturity='proposed' if barrier == 'lifecycle' else 'draft')
    options = arguments(root)
    if barrier == 'authority':
        options['authority'] = PublicationAuthority('denied', '1', lambda request: False)
    elif barrier == 'physical_base': (root / subject.path).write_bytes(subject.source_bytes + b'\n')
    else:
        options['gates'] = [ModelGate('lifecycle', 'reject',
            lambda c: c.dependency_result({key: [] for key in c.subjects}),
            lambda c: c.result([{'reason': 'review_required', 'severity': 'error'}]))]
    before = inventory(root)
    with pytest.raises((PublicationCheckError, TargetError)):
        update_artifact(supplied, operation(subject), **options)
    assert inventory(root) == before


@pytest.mark.parametrize('selected', [None, {}, {'old_allow': True},
    {**POLICY, 'format_version': '2.0.0'}, {**POLICY, 'allow_open': True}])
def test_policy_migration_requires_explicit_closed_versioned_value(selected):
    subject = DomainArtifact(canonical_json_bytes(domain_value('release')))
    with no_write_attempts(), pytest.raises(ModelError):
        prepare_readiness_policy_update(subject, selected)


@pytest.mark.parametrize('selected', [None, '', 'CLOSED', 'done', 'akzeptiert', True, 1])
@pytest.mark.parametrize('kind', ['risk', 'issue'])
def test_status_migration_never_guesses_legacy_aliases(kind, selected):
    parser, factory = (DomainArtifact, domain_value) if kind == 'risk' else (RecordArtifact, record_value)
    subject = parser(canonical_json_bytes(factory(kind)))
    with no_write_attempts(), pytest.raises(ModelError): prepare_readiness_status_update(subject, selected)


def test_migration_does_not_reissue_existing_blocker_decisions_or_evidence_implicitly():
    legacy = {'blocker_decisions': ['unclassified'], 'verification_evaluation': {'old': True}}
    subject = DomainArtifact(canonical_json_bytes(domain_value('release', readiness_policy=legacy)))
    before = subject.source_bytes
    prepared = prepare_readiness_policy_update(subject, POLICY)
    after = JsonPatch(prepared.data['patch']).apply(subject.data).data
    assert subject.source_bytes == before and subject.data['readiness_policy'] == legacy
    assert after['readiness_policy'] == POLICY and after['maturity'] == 'draft'
