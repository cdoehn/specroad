"""Least strong fixed point over explicit, byte-bound source observations.

No weak expansion/boundaries, configuration evaluator, review decision, model
root or transaction is implied. Unknown required providers fail closed.
"""
from dataclasses import dataclass
from hashlib import sha256
import re

from ..model.attachments import AttachmentDescriptor
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from ._scope_selector_contract import _artifact_id
from .closure_inputs import ClosureBindings, ClosureNode, artifact_node, resource_node
from .scope_seeds import ScopeSeeds, resolve_scope_seeds

STRONG_RELATIONS = frozenset((
    'addresses', 'refines', 'derived_from', 'depends_on', 'constrains',
    'allocated_to', 'implemented_by', 'verified_by', 'produces', 'mitigates',
    'scheduled_for', 'part_of', 'supersedes', 'contains', 'references',
))
WEAK_RELATIONS = frozenset(('conflicts_with', 'duplicates'))


@dataclass(frozen=True)
class StrongClosure:
    seeds: ScopeSeeds
    bindings_sha256: str
    artifact_ids: tuple
    resource_ids: tuple
    attachments: tuple
    pending_weak_relations: tuple
    processing_order: tuple

    @property
    def strong_closure_complete(self):
        return True

    @property
    def closure_complete(self):
        # Weak boundary policy is not certified by a strong-only result, even
        # when this particular input happens not to contain any weak edges.
        return False

    @property
    def validation_scope(self):
        return 'strong_closure_over_supplied_bindings'

    @property
    def atomic_snapshot(self):
        return False


def _array(value, pointer):
    if type(value) is not list:
        raise ModelError('closure_dependency_array_required', pointer=pointer)
    return value


def _artifact_target(identity, records, pointer, expected_type=None):
    _artifact_id(identity, expected_type)
    target = records.get(identity)
    if target is None:
        raise ModelError('closure_bound_artifact_missing', pointer=pointer)
    return artifact_node(identity)


def _field_dependencies(record, bindings, records):
    """Only schema-defined dependency locations are interpreted as links."""
    value = record.data
    if record.identity.artifact_type == 'evidence':
        subjects = _array(value.get('subjects'), '/subjects')
        if not subjects:
            raise ModelError('closure_evidence_subjects_required', pointer='/subjects')
        subject_ids = set()
        for number, subject in enumerate(subjects):
            pointer = '/subjects/' + str(number)
            if type(subject) is not dict or set(subject) != {
                    'artifact_id', 'revision', 'artifact_sha256', 'verification_context_sha256'}:
                raise ModelError('closure_evidence_subject_invalid', pointer=pointer)
            if type(subject['revision']) is not int or subject['revision'] < 1:
                raise ModelError('closure_evidence_subject_invalid', pointer=pointer + '/revision')
            for field in ('artifact_sha256', 'verification_context_sha256'):
                if type(subject[field]) is not str or re.fullmatch('[0-9a-f]{64}', subject[field]) is None:
                    raise ModelError('closure_evidence_subject_invalid', pointer=pointer + '/' + field)
            target = _artifact_target(subject['artifact_id'], records, pointer + '/artifact_id')
            if target.identity in subject_ids:
                raise ModelError('duplicate_closure_evidence_subject', pointer=pointer)
            subject_ids.add(target.identity)
            # Staleness of historical hashes is a verification question. It is
            # NOT a reason to lose the subject from the required scope.
            yield target
        by_path = {descriptor.path: (identity, descriptor)
                   for identity, descriptor in bindings.attachments.items()}
        seen = set()
        for number, data in enumerate(_array(value.get('attachments', []), '/attachments')):
            descriptor = AttachmentDescriptor.from_data(data)
            pointer = '/attachments/' + str(number)
            if descriptor.path in seen:
                raise ModelError('duplicate_closure_attachment', pointer=pointer)
            seen.add(descriptor.path)
            observed = by_path.get(descriptor.path)
            if observed is None:
                raise ModelError('closure_attachment_observation_missing', pointer=pointer)
            if observed[1] != descriptor:
                raise ModelError('closure_attachment_binding_mismatch', pointer=pointer)
            yield resource_node(observed[0])
    elif record.identity.artifact_type == 'verification':
        slots = _array(value.get('evidence_slots'), '/evidence_slots')
        if not slots:
            raise ModelError('closure_evidence_slots_required', pointer='/evidence_slots')
        checks = set()
        for number, slot in enumerate(slots):
            pointer = '/evidence_slots/' + str(number)
            if type(slot) is not dict or set(slot) != {'test_id', 'check_id', 'dimension'}:
                raise ModelError('closure_evidence_slot_invalid', pointer=pointer)
            check = slot['check_id']
            if type(check) is not str or re.fullmatch('[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', check) is None:
                raise ModelError('closure_evidence_slot_invalid', pointer=pointer + '/check_id')
            if check in checks:
                raise ModelError('duplicate_closure_check_id', pointer=pointer)
            checks.add(check)
            if type(slot['dimension']) is not str or not slot['dimension'].strip():
                raise ModelError('closure_evidence_slot_invalid', pointer=pointer + '/dimension')
            if slot['test_id'] is not None:
                yield _artifact_target(slot['test_id'], records, pointer + '/test_id', 'test')
    elif record.identity.artifact_type == 'baseline':
        if record.identity.id not in bindings.inventory.archive_bindings:
            raise ModelError('scope_baseline_archive_inventory_required')
        for identity in bindings.inventory.archive_bindings[record.identity.id]:
            yield resource_node(identity)


def _check_seeds(seeds, bindings):
    if type(seeds) is not ScopeSeeds or type(bindings) is not ClosureBindings:
        raise ModelError('closure_values_required')
    if seeds.inputs_sha256 != bindings.inventory.fingerprint:
        raise ModelError('stale_closure_seed_inputs')
    if seeds.descriptor.data['configuration_id'] is not None:
        raise ModelError('scope_configuration_resolver_required')
    if seeds.descriptor.scope_kind != 'query':
        if seeds != resolve_scope_seeds(seeds.descriptor, bindings.inventory):
            raise ModelError('closure_seed_selection_mismatch')
    # Query seeds originate at the separately bound QuerySeedPage boundary. They
    # retain page order; this function does not reexecute or repaginate queries.


def resolve_strong_closure(seeds, bindings):
    """Compute every strong reachable node or raise, without returning a prefix.

    Every reached usage/review observation must be explicit. Resource descriptors
    are provided by trusted readers; this function does not open their paths or
    infer current reviews from persisted maturity fields. Retired/rejected nodes
    remain reachable. Cyclic required dependency graphs terminate by identity.
    """
    _check_seeds(seeds, bindings)
    records = {record.identity.id: record for record in bindings.inventory.records}
    resources = {value.resource_id: value for value in bindings.inventory.resources}
    pending = {artifact_node(identity) for identity in seeds.artifact_ids}
    pending.update(resource_node(identity) for identity in seeds.resource_ids)
    visited, processing, weak = set(), [], set()
    while pending:
        node = min(pending, key=lambda item: item.order_key)
        pending.remove(node)
        if node in visited:
            continue
        if node.kind == 'artifact':
            record = records.get(node.identity)
            if record is None:
                raise ModelError('closure_bound_artifact_missing')
            # Preserve the pre-existing specification-scope safety boundary.
            # Its complete diagnostic/closure-policy integration is step 3.i.
            if (seeds.descriptor.scope_kind == 'specification'
                    and record.identity.artifact_type in ('proposal', 'baseline')):
                raise ModelError('scope_control_dependency')
        elif node.identity not in resources:
            raise ModelError('closure_bound_resource_missing')
        if node not in bindings.uses:
            raise ModelError('closure_usage_observation_missing')
        visited.add(node)
        processing.append(node)
        targets = list(bindings.uses[node])
        if node.kind == 'artifact':
            for relation in record.relations:
                relation_id = relation.identity.id
                if relation_id not in bindings.current_reviews:
                    raise ModelError('closure_review_observation_missing')
                targets.extend(artifact_node(identity) for identity in bindings.current_reviews[relation_id])
                if relation.type in STRONG_RELATIONS:
                    targets.append(artifact_node(relation.target))
                elif relation.type in WEAK_RELATIONS:
                    weak.add((node.identity, relation_id, relation.target))
                else:
                    raise ModelError('unsupported_closure_relation')
            targets.extend(_field_dependencies(record, bindings, records))
        elif resources[node.identity].kind == 'attachment' and node.identity not in bindings.attachments:
            raise ModelError('closure_attachment_observation_missing')
        pending.update(target for target in targets if target not in visited)
    artifact_ids = tuple(sorted((node.identity for node in visited if node.kind == 'artifact'),
                                key=lambda name: name.encode('utf-8')))
    resource_ids = tuple(sorted((node.identity for node in visited if node.kind == 'resource'),
                                key=lambda name: (name.encode('utf-8'), (resources[name].version or '').encode('utf-8'))))
    attachments = tuple(sorted((bindings.attachments[identity] for identity in resource_ids
                                if resources[identity].kind == 'attachment'), key=lambda item: item.path.encode('utf-8')))
    return StrongClosure(seeds, bindings.fingerprint, artifact_ids, resource_ids, attachments,
                         tuple(sorted(weak, key=lambda edge: tuple(item.encode('utf-8') for item in edge))), tuple(processing))
