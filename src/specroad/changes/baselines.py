"""Isolated working-Baseline planning; generic immutable writes stay closed."""
from base64 import b64decode, b64encode
from binascii import Error as Base64Error
from dataclasses import dataclass
from ..archive.objects import SnapshotObject
from ..archive.project_snapshot import build_project_baseline_manifest
from ..model.audit import new_artifact_audit, actor as parse_actor
from ..model.audit_values import UtcTimestamp
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.identity_values import artifact_identity
from ..model.versions import SCHEMA_VERSION
from ..validation import ModelDocument, ModelGate
from ._common import _artifact
from ._metadata_policy import bind_policy
from ._patch_values import _snapshot
from .lifecycle import prepare_change_lifecycle
from .metadata_values import MetadataArtifact
from .target_values import TargetError


def baseline_mode(operations):
    selected = any(op['op'] == 'baseline_create' for op in operations)
    if selected and len(operations) != 1:
        raise TargetError('baseline_requires_one_isolated_operation')
    return selected


def object_documents(operation):
    """Decode exact sorted content addresses; no paths or code from elsewhere."""
    result = []
    for row in operation['objects']:
        try:
            raw = b64decode(row['bytes_base64'], validate=True)
        except (ValueError, TypeError, Base64Error) as error:
            raise TargetError('baseline_object_encoding_invalid') from error
        item = SnapshotObject(raw)
        if (b64encode(raw).decode('ascii') != row['bytes_base64'] or
                item.reference.path != row['path']):
            raise TargetError('baseline_object_bytes_mismatch')
        result.append(ModelDocument(row['path'], raw))
    paths = [d.path for d in result]
    if paths != sorted(set(paths)):
        raise TargetError('baseline_object_inventory_invalid')
    return tuple(result)


def prepare_baseline_operation(model, *, baseline_id, name, actor, planned_at, configuration_id=None):
    snapshot = build_project_baseline_manifest(model, baseline_id=baseline_id,
                                              configuration_id=configuration_id)
    data = snapshot.data
    record = {'schema_version': SCHEMA_VERSION, 'id': baseline_id, 'id_scheme': 'random128-v1',
        'artifact_type': 'baseline', 'title': name, 'maturity': 'approved', 'baseline_state': 'sealed',
        **new_artifact_audit(actor=parse_actor(actor), planned_at=UtcTimestamp(planned_at)).as_fields(),
        'relations': [], 'extensions': {}, **{k: data[k] for k in (
            'baseline_kind', 'scope_descriptor', 'manifest', 'model_root_sha256',
            'configuration_hash', 'profiles', 'tool_version')}}
    _artifact(record, '/record', 'baseline')
    return {'op': 'baseline_create', 'record': record,
        'objects': [{'path': o.reference.path, 'bytes_base64': b64encode(o.content).decode('ascii')}
                    for o in snapshot.objects]}


@dataclass(frozen=True)
class _BaselineCandidates:
    _model: object
    candidates: tuple
    _history: tuple

    @property
    def artifacts(self): return self._model.data
    @property
    def metadata_applied(self): return True
    @property
    def decisions(self): return []
    @property
    def previously_approved_ids(self): return list(self._history)


def prepare_baseline_candidates(model, operations, *, metadata_policy_version,
        actor, planned_at, preconditions=()):
    if not baseline_mode(operations):
        raise TargetError('baseline_operation_required')
    metadata = bind_policy(metadata_policy_version, actor, planned_at)
    base = prepare_change_lifecycle(model.artifacts, [], **metadata,
        preconditions=preconditions, source_files=model.source_files, **model.reservations)
    record = operations[0]['record']
    identity = artifact_identity(record)
    if identity.id in set(base.previously_approved_ids):
        raise TargetError('baseline_identity_already_present')
    expected = prepare_baseline_operation(model, baseline_id=identity.id, name=record['title'],
        actor=metadata['actor'], planned_at=planned_at,
        configuration_id=record['scope_descriptor'].get('configuration_id'))
    if canonical_json_bytes(expected) != canonical_json_bytes(operations[0]):
        raise TargetError('baseline_snapshot_binding_mismatch')
    candidate = MetadataArtifact(identity.id, _snapshot(record), None,
        canonical_json_sha256(record), (0,), 'created')
    return _BaselineCandidates(_snapshot(sorted([*base.artifacts, record], key=lambda a: a['id'])),
                               (candidate,), tuple(base.previously_approved_ids))


def prepare_baseline_gates(model, operation, *, actor, planned_at, gates=()):
    """Certify this newly constructed record only, never old approvals/history.

    Existing approved artifacts or Baselines still need their trusted semantic
    providers. Host gates, when explicitly supplied, own their whole subject set.
    The planner independently recomputes the new record and all snapshot bytes.
    """
    owned = model.snapshot()
    value = operation.data
    identity = value['record']['id']
    bound = canonical_json_sha256({'sources': owned._sources_sha256, 'operation': value,
                                  'actor': actor, 'planned_at': planned_at})
    def dependencies(context):
        return context.dependency_result({key: list(context.all_ids) for key in context.subjects})
    def check(context):
        if context.subjects != (identity,):
            return context.result([{'reason': 'baseline_existing_subjects_require_service', 'severity': 'error'}])
        folded = prepare_baseline_candidates(owned, [value], metadata_policy_version='change-metadata-v1',
                                            actor=actor, planned_at=planned_at)
        if canonical_json_sha256({a['id']: a for a in folded.artifacts}) != canonical_json_sha256(
                {key: context.artifact(key) for key in context.all_ids}):
            return context.result([{'reason': 'baseline_target_mismatch', 'severity': 'error'}])
        return context.result()
    existing = {g.gate_id for g in gates if type(g) is ModelGate}
    prepared = tuple(ModelGate(name, 'bound-working-baseline-v1', dependencies, check, bound)
                     for name in ('lifecycle', 'baseline_integrity') if name not in existing)
    configuration_id = value['record']['scope_descriptor'].get('configuration_id')
    if configuration_id is not None:
        from ..configurations._gate_context import _ConfigurationGateContext
        from ..configurations.gates import _bound_configuration_gate
        from ..graph.relations import SourceRelations
        selected = _ConfigurationGateContext(tuple(SourceRelations(d.content, path=d.path)
                                                   for d in owned.documents), configuration_id)
        # A caller may add other semantic gates, but cannot replace the bound
        # selection check. Duplicate configuration providers remain an error.
        prepared += (_bound_configuration_gate(selected),)
    return prepared
