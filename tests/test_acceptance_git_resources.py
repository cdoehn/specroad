"""R-44/R-45 use actual separate Git roots and mandatory original resources."""
from hashlib import sha256
import pytest

from specroad.bundles.errors import BundleError
from specroad.changes import TargetModel, transaction_preflight
from specroad.cli.contracts import CommandClass
from specroad.configurations import resolve_configuration
from specroad.graph.relations import SourceRelations
from specroad.model.attachments import AttachmentDescriptor
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.qualification.project import validate_project
from specroad.storage.domain_artifact import DomainArtifact
from specroad.validation import ModelDocument
from specroad.verification import VerificationContext
from support.domain import domain_value
from support.git_restart import project_files, save, checkout, new_write
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.records import record_value
from test_git_restart import interrupted
from test_proposal_basis import project


@pytest.mark.parametrize('missing', [None, 'attachment', 'primary_document'])
def test_original_attachment_and_primary_document_are_required_in_a_fresh_git_root(tmp_path, monkeypatch, missing):
    source = tmp_path / 'interrupted-source'
    raw = b'\x00\xff original mandatory attachment\r\n'
    attachment = AttachmentDescriptor('attachments/original.bin', 'application/octet-stream',
                                      len(raw), sha256(raw).hexdigest())
    document = record_value('document')
    configuration = record_value('configuration')
    base = project(source, artifacts=[domain_value('goal'), domain_value('requirement'), configuration, document])
    records = tuple(SourceRelations(d.content, path=d.path) for d in base.documents)
    requirement = next(r for r in records if r.identity.artifact_type == 'requirement')
    context = VerificationContext(DomainArtifact(requirement.source_bytes, path=requirement.path),
        configuration=resolve_configuration(records, configuration['id']))
    evidence = record_value('evidence', subjects=[context.subject_binding],
        configuration_policy='bound', configuration_hash=context.data['configuration_hash'],
        attachments=[attachment.data])
    evidence_path = artifact_path('evidence', evidence['id'], 'SR')
    evidence_bytes = canonical_json_bytes(evidence)
    # Bind the descriptor and original bytes together before model validation.
    # The saved negative Evidence stays historical; no successful run is invented.
    model = TargetModel(base.configuration_bytes, base.binding,
        [*base.documents, ModelDocument(evidence_path, evidence_bytes)], profile=base.profile,
        resource_files=[*base.resource_files, ModelDocument(attachment.path, raw)], attachments=[attachment])
    for path, content in model.source_files.items():
        put(source, path, content)
    assert new_write(source, 'saved-request', 'saved-transaction', 'Saved complete project')['commit_completed']
    commit, original = save(source)
    assert original[attachment.path] == raw and original[evidence_path] == evidence_bytes
    with no_write_attempts(): validate_project(original)
    interrupted(source, monkeypatch)
    damaged = inventory(source)
    fresh = checkout(source, tmp_path / 'fresh', commit)
    assert project_files(fresh) == original
    if missing is not None:
        path = attachment.path if missing == 'attachment' else artifact_path('document', document['id'], 'SR')
        (fresh / path).unlink()
    before = inventory(fresh)
    with no_write_attempts():
        if missing is None:
            validate_project(project_files(fresh))
        else:
            with pytest.raises((ModelError, BundleError)):
                validate_project(project_files(fresh))
    assert inventory(fresh) == before
    if missing is None:
        result = new_write(fresh, 'new-root-intent', 'new-root-transaction', 'New explicit root intent')
        assert result['commit_completed'] and not result['replayed']
        assert (fresh / attachment.path).read_bytes() == raw
        assert (fresh / evidence_path).read_bytes() == evidence_bytes
        assert (fresh / artifact_path('document', document['id'], 'SR')).read_bytes() == original[artifact_path('document', document['id'], 'SR')]
    with no_write_attempts():
        blocked = transaction_preflight(source, command_class=CommandClass.NORMATIVE_WRITE)
    assert blocked.exit_code == 5 and inventory(source) == damaged
