"""Native preservation inventory over owned bytes; never a publication grant."""
from dataclasses import dataclass
from hashlib import sha256
import json

from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..model.audit_values import Actor, UtcTimestamp
from ..changes.metadata_time import next_update_time
from ..storage.json_syntax import parse_json_object as parsed
from .plan_values import (STEP, SOURCE_CONTRACT, MANIFEST_PATH, require, owned_files,
                          file_bindings, unb64)
from .plan_contract import validate_inputs
from .plan_inputs import target_contract
from .reference01 import inventory_bytes
from .relation_derivation import _SourceRelations
from .plan_originals import _original_archive


class LossInventory:
    """Ordered detached JSON observations; interpretation belongs to each caller."""
    def __init__(self):
        self._rows = []

    def append(self, row):
        self._rows.append(jcs(row))

    @property
    def rows(self):
        return [json.loads(raw) for raw in self._rows]


def _pointer(name):
    return '/' + name.replace('~', '~0').replace('/', '~1')


def _differences(before, after, pointer=''):
    """Exact JSON values, atomic ordered arrays, presence separate from null."""
    if jcs(before) == jcs(after):
        return
    if type(before) is dict and type(after) is dict:
        for key in sorted(set(before) | set(after), key=lambda s: s.encode('utf-8')):
            at = pointer + _pointer(key)
            if key not in before or key not in after:
                yield at, {'present': key in before, 'value': before.get(key)}, {
                    'present': key in after, 'value': after.get(key)}
            else:
                yield from _differences(before[key], after[key], at)
    else:
        yield pointer, {'present': True, 'value': before}, {'present': True, 'value': after}


@dataclass(frozen=True, init=False)
class MigrationLossReport:
    """Detached native observation; there is deliberately no saved-report loader."""
    _encoded: bytes

    @classmethod
    def _create(cls, binding, rows):
        ordered = sorted(rows, key=lambda r: tuple(r[k].encode('utf-8')
                         for k in ('path', 'pointer', 'hash_domain')))
        keys = [(r['path'], r['pointer'], r['hash_domain']) for r in ordered]
        require(len(keys) == len(set(keys)), 'migration_loss_conflict')
        losses = [{'loss_id': 'LOSS-' + digest(['migration-loss-v1', binding, r]), **r}
                  for r in ordered]
        value = {'format_version': 'migration-loss-report-v1', 'binding': binding,
            'losses': losses, 'lossless': not losses, 'write_authorized': False,
            'approval_granted': False}
        result = object.__new__(cls)
        object.__setattr__(result, '_encoded', jcs({**value, 'report_sha256': digest(value)}))
        return result

    @property
    def data(self):
        return parsed(self._encoded)

    @property
    def sha256(self):
        return self.data['report_sha256']

    @property
    def lossless(self):
        return self.data['lossless']

    @property
    def write_authorized(self):
        return False

    def __bool__(self):
        raise TypeError('A preservation observation is not write authorization')


def _expected_artifact(original, relations, inputs, actor, planned_at):
    """The closed 12.20.2 exception list, independent of the transforming stamp."""
    old = original.data
    value = json.loads(jcs(old))
    value.update(schema_version='0.2.0', id_scheme='legacy-sequential-v1',
        revision=int(old['revision']) + 1, updated_by=actor,
        updated_at=next_update_time(planned_at, old['updated_at']))
    if old['maturity'] == 'approved':
        value['maturity'] = 'draft'
    value['relations'] = relations.materialize(original)
    if old['artifact_type'] == 'requirement':
        mapping = next(r for r in inputs['requirement_mappings'] if r['artifact_id'] == old['id'])
        for key in ('language', 'normative_force', 'statement'):
            value[key] = mapping[key]
    if old['artifact_type'] == 'proposal':
        from ..changes.values import ChangePlan
        from ..proposals.values import content_sha256
        mapping = next(r for r in inputs['proposal_mappings'] if r['artifact_id'] == old['id'])
        bound = ChangePlan(jcs(mapping['change_plan'])).data
        value.update(base=bound['base'], change_plan=bound,
            content_revision=int(old['content_revision']) + 1,
            proposal_status='draft', maturity='draft')
        value['content_sha256'] = content_sha256(value)
    return value


def _assess_qualified(inventory, source, candidate, inputs, actor, planned_at, relations):
    """Internal seam: inputs and source have already passed native qualification."""
    rows, byte_expectations, json_expectations = LossInventory(), dict(source), {}
    original_archive, manifest, _ = _original_archive(inventory, source, target_contract(), relations)
    byte_expectations.update(original_archive)
    byte_expectations.update({r['path']: unb64(r['bytes_base64']) for r in inputs['target_resources']})
    for original in inventory.originals:
        if original.snapshot_root != inventory.model_root_sha256:
            continue
        if original.role == 'artifact' and original.classification == 'mutable':
            value = _expected_artifact(original, relations, inputs, actor, planned_at)
            json_expectations[original.path] = value
            byte_expectations.pop(original.path, None)
            if value['artifact_type'] == 'proposal':
                manifest['proposal_transitions'].append({'artifact_id': value['id'],
                    'source_revision': original.data['revision'], 'source_sha256': original.canonical_sha256,
                    'target_revision': value['revision'], 'target_content_revision': value['content_revision']})
    manifest['proposal_transitions'].sort(key=lambda r: r['artifact_id'])
    json_expectations[MANIFEST_PATH] = manifest
    config = parsed(unb64(inputs['target_configuration']))
    old_extensions = parsed(source['specroad.json'])['extensions']
    if old_extensions:
        # Source namespaces are required values, never defaults or inferred mappings.
        config['extensions'] = {**config.get('extensions', {}), **old_extensions}
    json_expectations['specroad.json'] = config
    byte_expectations.pop('specroad.json', None)
    byte_expectations.pop('profiles/core-reference01.json', None)
    for path, raw in byte_expectations.items():
        actual = candidate.get(path)
        if raw == actual:
            continue
        def observed(content):
            return {'present': content is not None, 'value': None if content is None else {
                'size': len(content), 'sha256': sha256(content).hexdigest()}}
        rows.append({'path': path, 'pointer': '', 'reason': 'missing' if actual is None else 'changed',
            'hash_domain': 'bytes', 'before': observed(raw), 'after': observed(actual)})
    for path, expected in json_expectations.items():
        if path not in candidate:
            differences = [('', {'present': True, 'value': expected}, {'present': False, 'value': None})]
        else:
            differences = _differences(expected, parsed(candidate[path]))
        for pointer, before, after in differences:
            rows.append({'path': path, 'pointer': pointer,
                'reason': 'changed' if after['present'] else 'missing',
                'hash_domain': 'json', 'before': before, 'after': after})
    binding = {'step_id': STEP, 'source_contract': SOURCE_CONTRACT, 'target_contract': target_contract(),
        'source_model_root_sha256': inventory.model_root_sha256,
        'source_files_sha256': digest(file_bindings(source)),
        'target_files_sha256': digest(file_bindings(candidate)), 'inputs_sha256': digest(inputs)}
    return MigrationLossReport._create(binding, rows.rows)


def assess_migration_preservation(files, candidate, *, inputs, actor, planned_at):
    """Requalify real owned sources and enumerate a complete candidate's losses.

    This is not target-schema validation or permission to execute the candidate.
    Serialized reports cannot be substituted for native source observations.
    """
    source, target = owned_files(files), owned_files(candidate)
    inputs = parsed(jcs(inputs)); validate_inputs(inputs)
    require(type(actor) is dict and set(actor) == {'actor_type', 'actor_id'}, 'migration_actor_required')
    actor = Actor(**actor).as_fields(); UtcTimestamp(planned_at)
    inventory = inventory_bytes(source)
    from .planning import _mapping_index
    from .plan_inputs import _target
    originals = tuple(o for o in inventory.originals if o.snapshot_root == inventory.model_root_sha256)
    _, blockers = _target(inputs, inventory.data['project_id'], parsed(source['specroad.json'])['id_prefix'])
    for kind in ('requirement', 'proposal'):
        _, missing = _mapping_index(inputs[kind+'_mappings'], originals, kind)
        blockers += missing
    require(not blockers, 'migration_loss_inputs_incomplete')
    return _assess_qualified(inventory, source, target, inputs, actor, planned_at, _SourceRelations(inventory))
