"""Full byte candidates and independent read-only writer preparation for K.3."""
from hashlib import sha256

from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..model.errors import ModelError
from ..model.audit import artifact_audit
from ..model.history_protection import protected_record
from ..storage.json_syntax import parse_json_object as parsed
from ..changes.merge_metadata import AUDIT, POLICY, merge_creation, combined_merge_audit
from ..changes.metadata_values import MetadataError
from ..bundles._payload_model import owned_payload_model
from ..bundles.errors import BundleError
from .field_values import _MISSING
from .conflict_schema import ROLES
from .conflicts import _originals, _rules
from .relation_inputs import _sources
from .resolutions import read_merge_resolutions, MergeResolutions
from ._field_merge import merge_owned

from .metadata_values import MergeMetadata

FORMAT = 'merge-metadata-candidates-v1'




def _input(raw, sources, history, expected):
    if type(raw) is not bytes:
        raise ModelError('merge_metadata_input_bytes_required')
    if sha256(raw).hexdigest() != expected:
        raise ModelError('merge_metadata_input_hash_mismatch')
    plan = read_merge_resolutions(raw, sources, history=history, expected_plan_sha256=digest(parsed(raw)))
    data = plan.data
    resolved = type(plan) is MergeResolutions
    catalogue = data['catalogue'] if resolved else data
    events = data['resolutions'] if resolved else []
    targets = data['targets'] if resolved else []
    unresolved = data['unresolved_conflict_ids'] if resolved else [row['conflict_id'] for row in catalogue['conflicts']]
    return data, catalogue, events, targets, unresolved


def _replace(target, pointer, value):
    if not pointer:
        return value
    parts = [part.replace('~1', '/').replace('~0', '~') for part in pointer[1:].split('/')]
    current = target
    for part in parts[:-1]:
        if type(current) is not dict or part not in current:
            raise MetadataError('merge_metadata_resolution_path')
        current = current[part]
    if type(current) is not dict:
        raise MetadataError('merge_metadata_resolution_path')
    current[parts[-1]] = value
    return target


def _select(raw, forced):
    old, left, right = (raw.get(role) for role in ROLES)
    if not forced:
        if left is not None and (left == right or right is None or old == right):
            return 'unchanged_ours', 'ours'
        if right is not None and (left is None or old == left):
            return 'adopt_existing', 'theirs'
    return 'combined', None


def _candidate(values, targets, *, artifact=False):
    prepared = {}
    for role, value in values.items():
        prepared[role] = ({key: item for key, item in value.items() if key not in AUDIT | {'relations'}}
                          if artifact and type(value) is dict else value)
    candidate, failures = merge_owned(*(prepared[role] for role in ROLES),
                                      rules=_rules(prepared['ours']) if artifact else None)
    replacements = {row['pointer']: row['value'] for row in targets}
    for failure in failures:
        if failure.pointer not in replacements:
            raise MetadataError('merge_metadata_unresolved_field')
    for pointer, value in replacements.items():
        if value.get('state') != 'present' or value.get('domain') != 'json-v1':
            raise MetadataError('merge_metadata_json_target_required')
        candidate = _replace(candidate, pointer, value['value'])
    if candidate is _MISSING:
        raise MetadataError('merge_metadata_target_missing')
    return candidate


def _known_revision(sources, values, identifier):
    """Only native, content-bound Ours Baselines can contribute history."""
    from ..archive.objects import SnapshotObject
    from ..archive.verification import verify_baseline_objects
    known = max((artifact_audit(values[role]).revision.value for role in ('base', 'ours')
                 if values[role] is not None), default=0)
    files = sources.ours.files
    objects = None
    for path, raw in sorted(files.items()):
        if not path.startswith('spec/'):
            continue
        record = parsed(raw)
        if record.get('artifact_type') != 'baseline':
            continue
        rows = [row for row in record.get('manifest', [])
                if row.get('role') == 'artifact' and row.get('id') == identifier]
        if not rows:
            continue
        if objects is None:
            objects = [SnapshotObject(content) for name, content in files.items()
                       if name.startswith('archive/objects/')]
        # Reconstruct its native historical model root, not just row hashes.
        verify_baseline_objects(raw, objects)
        for row in rows:
            historical = parsed(files[row['object_path']])
            if (historical.get('id') != identifier or historical.get('artifact_type') != values['theirs']['artifact_type']
                    or historical.get('schema_version') != values['theirs']['schema_version']):
                raise MetadataError('merge_historical_identity_mismatch')
            merge_creation((*values.values(), historical))
            if protected_record(historical) or protected_record(values['theirs']):
                # Existing immutable history is also an original, even when
                # its identity is absent from the current Ours artifact set.
                if files[row['object_path']] != sources.theirs.files.get(row['source_path']):
                    raise MetadataError('merge_immutable_history_conflict')
            known = max(known, artifact_audit(historical).revision.value)
    return known


def prepare_merge_metadata(raw, sources, *, history, expected_plan_sha256):
    """Recompute full candidate bytes; never materialize a current project."""
    data, catalogue, events, targets, unresolved = _input(raw, sources, history, expected_plan_sha256)
    observed, relations, _ = _sources(sources)
    rows, conflicts, files = [], [], {}
    by_conflict = {row['conflict_id']: row for row in catalogue['conflicts']}
    for identifier in unresolved:
        conflicts.append({'identity': by_conflict[identifier]['identity'], 'reason': 'unresolved_conflict',
                          'conflict_id': identifier})
    if conflicts:
        # A relation conflict blocks its storage owner, not a fictitious file.
        blocked = {}
        for identifier in unresolved:
            conflict = by_conflict[identifier]
            identity = conflict['identity']
            if identity['kind'] == 'relation':
                affected = [{'kind': 'artifact', 'id': owner, 'version': None}
                            for owner in conflict['artifact_ids']]
            else:
                affected = [identity]
            for item in affected:
                key = jcs(item)
                observation = next(observed[role][key][1] for role in ('ours', 'theirs', 'base')
                                   if key in observed[role])
                blocked[key] = {'identity': item, 'path': observation['path'],
                                'classification': 'conflict', 'byte_sha256': None, 'size': None}
        rows = [blocked[key] for key in sorted(blocked)]
    if not conflicts:
        keys = sorted(set().union(*(set(observed[role]) for role in ROLES)))
        identities = {key: next(observed[role][key][0] for role in ROLES if key in observed[role]) for key in keys}
        decisions, actors = {}, {}
        for target in targets:
            decisions.setdefault(jcs(target['identity']), []).append(target)
        for event in events:
            row = by_conflict[event['conflict_id']]
            actors[jcs(row['identity'])] = event['actor']
            if row['identity']['kind'] == 'relation':
                for owner in row['artifact_ids']:
                    actors[jcs({'kind': 'artifact', 'id': owner, 'version': None})] = event['actor']
        merged_relations = {}
        for key in keys:
            identity = identities[key]
            if identity['kind'] != 'relation':
                continue
            values = _originals(sources, observed, relations, key)
            try:
                merged = _candidate(values, decisions.get(key, []))
                merged_relations.setdefault(merged['owner_id'], []).append(merged['relation'])
            except MetadataError as error:
                conflicts.append({'identity': identity, 'reason': error.reason})
        for key in keys:
            identity = identities[key]
            if identity['kind'] == 'relation':
                continue  # Relations are stored within their actual owner file.
            values = _originals(sources, observed, relations, key)
            observations = {role: observed[role][key][1] for role in ROLES if key in observed[role]}
            raw_values = {role: getattr(sources, role).files[obs['path']] for role, obs in observations.items()}
            path = next(observations[role]['path'] for role in ('ours', 'theirs', 'base') if role in observations)
            classification, selected = _select(raw_values, key in actors)
            row = {'identity': identity, 'path': path, 'classification': classification,
                   'byte_sha256': None, 'size': None}
            try:
                artifact = identity['kind'] == 'artifact'
                originals = {role: None if value is _MISSING else value for role, value in values.items()}
                protected = any(obs['storage_class'] == 'legacy_immutable' for obs in observations.values())
                protected = protected or artifact and any(type(value) is dict and protected_record(value) for value in originals.values())
                if artifact and all(value is None or type(value) is dict for value in originals.values()):
                    merge_creation(tuple(originals.values()))
                    if classification == 'adopt_existing':
                        known = _known_revision(sources, originals, identity['id'])
                        if artifact_audit(originals['theirs']).revision.value < known:
                            raise MetadataError('merge_lower_known_revision')
                if selected is not None:
                    content = raw_values[selected]
                else:
                    if protected:
                        raise MetadataError('merge_protected_metadata_change')
                    if any(type(value) is bytes for value in originals.values()):
                        choice = decisions.get(key, [])
                        if len(choice) != 1 or choice[0]['pointer'] != '':
                            raise MetadataError('merge_metadata_binary_target_required')
                        chosen = choice[0]['value']
                        matching = [value for value in raw_values.values()
                                    if chosen == {'state': 'present', 'domain': 'bytes-v1',
                                                  'size': len(value), 'sha256': sha256(value).hexdigest()}]
                        if not matching:
                            raise MetadataError('merge_metadata_binary_binding')
                        content = matching[0]
                    else:
                        value = _candidate(values, decisions.get(key, []), artifact=artifact)
                        if artifact:
                            value['relations'] = sorted(merged_relations.get(identity['id'], []), key=lambda item: item['relation_id'])
                            value.update(combined_merge_audit(*(originals[role] for role in ROLES),
                                                             resolution_actor=actors.get(key)))
                        content = jcs(value)
                if path in files:
                    raise MetadataError('merge_metadata_path_collision')
                files[path] = content
                row.update(byte_sha256=sha256(content).hexdigest(), size=len(content))
            except (ModelError, BundleError) as error:
                row['classification'] = 'conflict'
                conflicts.append({'identity': identity, 'reason': error.reason})
            rows.append(row)
    root = None
    if not conflicts:
        try:
            keys = tuple(sources.ours.binding['baseline']['profile_keys']) if sources.ours.kind == 'baseline' else None
            model = owned_payload_model(files, source_label='merge-metadata-candidate', profile_keys=keys)
            root = model.manifest(model.artifacts, sources.ours.binding['scope_descriptor']).sha256
        except (ModelError, BundleError) as error:
            conflicts.append({'identity': None, 'reason': 'merge_metadata_target_projection', 'detail': error.reason})
    if conflicts:
        files = {}
    file_rows = [{'path': path, 'sha256': sha256(content).hexdigest(), 'size': len(content)} for path, content in sorted(files.items())]
    result = {'metadata_format_version': FORMAT, 'metadata_policy_version': POLICY,
              'input_plan': data, 'input_plan_sha256': sha256(raw).hexdigest(),
              'resources': rows, 'resources_sha256': digest(rows), 'target_files': file_rows,
              'target_files_sha256': digest(file_rows), 'expected_target_model_root_sha256': root,
              'conflicts': sorted(conflicts, key=jcs), 'metadata_complete': not conflicts,
              'pending_gates': ([] if not conflicts else ['merge_metadata']) + ['target_validation', 'publication'],
              'ready': False, 'write_authorized': False, 'approval_granted': False}
    for role in ROLES:
        getattr(sources, role).verify_current()
    return MergeMetadata._create(result, files)


def verify_merge_metadata(candidate_raw, raw, sources, *, history, expected_plan_sha256):
    """Writer's read-only boundary: recompute from sources, not candidate values."""
    if type(candidate_raw) is not bytes:
        raise ModelError('merge_metadata_candidate_bytes_required')
    stored = parsed(candidate_raw)
    rebuilt = prepare_merge_metadata(raw, sources, history=history, expected_plan_sha256=expected_plan_sha256)
    if jcs(stored) != rebuilt.canonical_bytes:
        raise ModelError('merge_metadata_binding_mismatch')
    for role in ROLES:
        getattr(sources, role).verify_current()
    return rebuilt
