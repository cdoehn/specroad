"""Complete, read-only merge inventory; not a resolved or executable change plan."""
from dataclasses import dataclass
from hashlib import sha256

from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..model.errors import ModelError
from ..model.identity_tokens import decode128
from ..storage.json_syntax import parse_json_object
from .sources import MergeSources
from ..snapshots.inventory import source_resource_rows


ROLES = ('base', 'ours', 'theirs')
FORMAT = 'merge-inventory-v1'
BINDING_FIELDS = ('path', 'pointer', 'size', 'byte_sha256', 'value_sha256',
                  'value_domain', 'owner_id', 'id_scheme', 'storage_class')


def _plan_id(value):
    if type(value) is not str or not value.startswith('MP-'):
        raise ModelError('merge_inventory_plan_id')
    decode128(value[3:])
    return value


def _absent():
    return {'state': 'absent', **dict.fromkeys(BINDING_FIELDS)}



def _signature(identity, observation):
    if observation['state'] == 'absent':
        return None
    names = (('value_sha256', 'owner_id', 'id_scheme', 'storage_class')
             if identity['kind'] == 'relation' else
             ('path', 'byte_sha256', 'value_domain', 'id_scheme', 'storage_class'))
    return tuple(observation[name] for name in names)


@dataclass(frozen=True, init=False)
class MergeInventory:
    _encoded: bytes

    @classmethod
    def _create(cls, value):
        result = object.__new__(cls)
        object.__setattr__(result, '_encoded', jcs(value))
        return result

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def canonical_bytes(self):
        return self._encoded

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    @property
    def ready(self):
        return False

    @property
    def write_authorized(self):
        return False

    def __bool__(self):
        raise TypeError('A merge inventory is not a resolved merge or write authority')


def build_merge_inventory(sources, *, plan_id):
    """Bind all original files and native relations without inventing deletions."""
    if not sources_type(sources):
        raise ModelError('merge_sources_required')
    _plan_id(plan_id)
    observed = {}
    for role in ROLES:
        source = getattr(sources, role)
        verify_observation(source)
        observed[role], _ = source_resource_rows(source)
    rows = []
    for key in sorted(set().union(*(set(observed[role]) for role in ROLES))):
        identity = next(observed[role][key][0] for role in ROLES if key in observed[role])
        values = {role: observed[role][key][1] if key in observed[role] else _absent() for role in ROLES}
        signatures = [_signature(identity, values[role]) for role in ROLES]
        same = all(value is not None for value in signatures) and signatures[0] == signatures[1] == signatures[2]
        reasons = [] if same else ['semantic_planning_required']
        if any(values[role]['state'] == 'absent' for role in ROLES):
            reasons.append('absence_not_deletion')
        rows.append({'identity': identity, **values,
            'target_classification': 'unchanged_ours' if same else 'conflict',
            'pending_reasons': reasons})
    bindings = sources.binding
    files = [getattr(sources, role).files for role in ROLES]
    roots = [bindings[role]['model_root_sha256'] for role in ROLES]
    expected = roots[1] if files[0] == files[1] == files[2] and roots[0] == roots[1] == roots[2] else None
    for role in ROLES:
        verify_observation(getattr(sources, role))
    return MergeInventory._create({'inventory_format_version': FORMAT, 'plan_id': plan_id,
        'metadata_policy_version': 'merge-metadata-v1', 'project_id': sources.ours.project_id,
        'schema_version': sources.ours.schema_version, 'source_bindings': bindings,
        'source_bindings_sha256': digest(bindings), 'resources': rows,
        'inventory_sha256': digest(rows), 'expected_target_model_root_sha256': expected,
        'ready': False, 'write_authorized': False})


def read_merge_inventory(raw, sources):
    """Rebuild against original native sources; rehashed claims are not proof."""
    if type(raw) is not bytes:
        raise ModelError('merge_inventory_bytes_required')
    value = parse_json_object(raw)
    if value.get('inventory_format_version') != FORMAT:
        raise ModelError('merge_inventory_version')
    expected = build_merge_inventory(sources, plan_id=value.get('plan_id'))
    # Comparing exact canonical bytes also rejects extra/missing fields, false
    # versus zero, reordered rows, duplicate keys and noncanonical encodings.
    if raw != expected.canonical_bytes:
        raise ModelError('merge_inventory_binding_mismatch')
    return expected

from ._recorded import sources_type

from ._recorded import verify_observation
