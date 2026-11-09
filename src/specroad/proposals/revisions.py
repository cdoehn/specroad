"""Prepare owned physical/content revisions, without publishing or granting rights.

Control callers still owe native check/review evidence and the writer lock.
An original or a prepared revision is never proof of a human decision.
"""
from dataclasses import dataclass

from ..changes.metadata_time import next_update_time
from ..model.audit_values import Actor, Revision, UtcTimestamp
from ..model.canonical import canonical_json_bytes
from ..storage.json_syntax import parse_json_object
from .values import ProposalOriginal, content_sha256, require


_MANAGED = ('schema_version', 'id', 'id_scheme', 'artifact_type', 'revision',
            'created_at', 'created_by', 'updated_at', 'updated_by',
            'content_revision', 'content_sha256')
_CONTROL = ('maturity', 'proposal_status', 'reviews', 'control_history')


@dataclass(frozen=True, init=False)
class ProposalRevision:
    """A checked before/after pair; byte ownership survives caller mutations."""
    before: ProposalOriginal
    after: ProposalOriginal

    def __init__(self, original, candidate, *, expected_revision, actor, planned_at):
        require(type(original) is ProposalOriginal, 'proposal_original_required')
        require(type(expected_revision) is Revision, 'proposal_expected_revision_required')
        require(type(actor) is Actor and type(planned_at) is UtcTimestamp,
                'proposal_explicit_audit_required')
        before = original.data
        require(expected_revision.value == before['revision'],
                'proposal_revision_conflict', exit_code=6)
        require(type(candidate) is dict, 'proposal_object_required')
        value = parse_json_object(canonical_json_bytes(candidate))
        for field in _MANAGED:
            require(field in value and value[field] == before[field],
                    'proposal_managed_field_changed', pointer='/' + field)
        changed = canonical_json_bytes(value) != canonical_json_bytes(before)
        if changed:
            require(before['proposal_status'] not in ('rejected', 'stale', 'applied'),
                    'proposal_terminal_revision_changed')
            digest = content_sha256(value)
            content_changed = digest != before['content_sha256']
            for field in ('reviews', 'control_history'):
                old, new = before.get(field, []), value.get(field, [])
                require(type(new) is list and new[:len(old)] == old,
                        'proposal_history_rewritten', pointer='/' + field)
            if content_changed:
                require(before['proposal_status'] in ('draft', 'in_review', 'approved'),
                        'proposal_authoring_status_invalid')
                require(all(value.get(field) == before.get(field) for field in _CONTROL),
                        'proposal_content_and_control_mixed')
                value.update(maturity='draft', proposal_status='draft')
            require(value.get('proposal_status') not in ('validated', 'checked'),
                    'proposal_review_start_incomplete')
            value.update(revision=Revision(before['revision']).value + 1,
                         content_revision=Revision(before['content_revision']).value + int(content_changed),
                         content_sha256=digest,
                         updated_at=next_update_time(planned_at.value, before['updated_at']),
                         updated_by=actor.as_fields())
            after = ProposalOriginal(canonical_json_bytes(value), path=original.path)
        else:
            after = original
        object.__setattr__(self, 'before', original)
        object.__setattr__(self, 'after', after)

    @property
    def changed(self):
        return self.before.source_bytes != self.after.source_bytes

    @property
    def content_changed(self):
        return self.before.binding.content_sha256 != self.after.binding.content_sha256

    @property
    def write_authorized(self):
        return False
