"""Concrete, recorded targets for an explicitly forced saved plan.

The result records and specialist source rows are part of the hash-bound plan.
They are not a license to rebase its operations on a different live model.
All live bytes are still inventoried and qualified by the common writer.
"""
from hashlib import sha256

from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..model.errors import ModelError
from ..model.paths import artifact_path
from ..storage.json_syntax import parse_json_object
from .force_target import effect_path
from .write_guard_values import require


def _records(files):
    records = {}
    try:
        prefix = parse_json_object(files['specroad.json'])['id_prefix']
    except (KeyError, ModelError):
        return records
    for path, raw in files.items():
        if not path.endswith('.json'):
            continue
        try:
            value = parse_json_object(raw)
        except ModelError:
            continue
        identity = value.get('id')
        if type(identity) is str and type(value.get('artifact_type')) is str:
            try:
                managed = artifact_path(value['artifact_type'], identity, prefix) == path
            except ModelError:
                managed = False
            if managed:
                records.setdefault(identity, []).append((path, value))
    return records


def _decision(decisions, permitted, gate, subject, observed, requested):
    return decisions.decide(permitted, gate_id=gate, diagnostic_code='CORE_CONFLICT',
        subject=subject, operation='change.apply', observed_binding=observed,
        requested_binding=requested, effect='publish_recorded_target_without_rebase')


def _preconditions(data, before, records, decisions):
    for row in data['preconditions']:
        if row['kind'] == 'artifact':
            identity = row['artifact_id']
            matches = records.get(identity, [])
            require(len(matches) <= 1, 'force_ambiguous_artifact_target', exit_code=6)
            actual = None if not matches else matches[0][1]
            observed = None if actual is None else {
                'revision': actual.get('revision'), 'sha256': digest(actual)}
            requested = {k.removeprefix('expected_'): v for k, v in row.items()
                if k in ('expected_revision', 'expected_sha256')}
            permitted = observed is not None and all(observed[k] == v for k, v in requested.items())
            _decision(decisions, permitted, 'stale:artifact_precondition', identity, observed, requested)
        else:
            path = row['path']
            actual = before.get(path)
            observed = 'absent' if actual is None else sha256(actual).hexdigest()
            requested = 'absent' if row['kind'] == 'absent' else row['expected_byte_sha256']
            _decision(decisions, observed == requested, 'hash:file_precondition', path, observed, requested)


def recorded_target(plan, before, decisions):
    """Select only complete, explicit target records; never infer a repair.

    Unresolvable identities and missing physical specialist inputs remain
    errors. A negative product policy is separately retained as a finding.
    """
    data = plan.data
    records = _records(before)
    _preconditions(data, before, records, decisions)
    operations = data['operations']
    if any(op['op'] in ('schema_migrate', 'merge_publish') for op in operations):
        return _specialist_target(data, before, decisions)
    if any(op['op'] == 'plan_edit' for op in operations):
        return _plan_target(data, before, decisions)
    try:
        config = parse_json_object(before['specroad.json'])
        prefix = config['id_prefix']
    except (KeyError, ModelError) as error:
        from .write_guard_values import WriteGuardError
        raise WriteGuardError('force_explicit_resource_target_required', exit_code=3) from error
    target = dict(before)
    for row in data['result_artifacts']:
        value = row['artifact']; identity = value['id']
        matches = records.get(identity, [])
        require(len(matches) <= 1, 'force_ambiguous_artifact_target', exit_code=6)
        # A saved typed result carries an identity, not an arbitrary file path.
        path = matches[0][0] if matches else artifact_path(value['artifact_type'], identity, prefix)
        effect_path(path)
        target[path] = jcs(value)
    for operation in operations:
        if operation['op'] == 'representation_normalize':
            from ..model.representation import NormalizationCandidate
            path = operation['path']; effect_path(path)
            require(path in before, 'force_normalization_original_unavailable', exit_code=3)
            candidate = NormalizationCandidate(path, before[path])
            _decision(decisions, candidate.expected_byte_sha256 == operation['expected_byte_sha256'],
                'hash:normalization_source', path, candidate.expected_byte_sha256, operation['expected_byte_sha256'])
            require(candidate.result_byte_sha256 == operation['target_byte_sha256'],
                'force_explicit_normalization_target_unavailable', exit_code=3)
            target[path] = candidate.normalized_bytes
        if operation['op'] == 'baseline_create':
            from .baselines import object_documents
            for document in object_documents(operation):
                effect_path(document.path)
                target[document.path] = document.content
    return target


def _plan_target(data, before, decisions):
    require(len(data['operations']) == 1, 'force_explicit_plan_program_required', exit_code=2)
    operation = data['operations'][0]
    target = dict(before)
    for row in operation['sources']:
        path = row['path']; effect_path(path)
        actual = before.get(path)
        expected = None if row['before'] is None else row['before'].encode('utf-8')
        observed = 'absent' if actual is None else sha256(actual).hexdigest()
        requested = 'absent' if expected is None else sha256(expected).hexdigest()
        _decision(decisions, actual == expected, 'stale:plan_source', path, observed, requested)
        if row['after'] is None:
            target.pop(path, None)
        else:
            target[path] = row['after'].encode('utf-8')
    return target


def _specialist_target(data, before, decisions):
    require(len(data['operations']) == 1, 'force_explicit_specialist_program_required', exit_code=2)
    operation = data['operations'][0]
    # Both native specialists bind full target bytes in each change row;
    # they do not need a second projection or an inferred live-source rebase.
    from ..migration.plan_values import unb64
    target = dict(before)
    for row in operation['changes']:
        path = row['path']; effect_path(path)
        actual = before.get(path)
        observed = None if actual is None else sha256(actual).hexdigest()
        _decision(decisions, observed == row['before_sha256'], 'stale:specialist_source',
            path, observed, row['before_sha256'])
        if row['after_bytes_base64'] is None:
            target.pop(path, None)
        else:
            target[path] = unb64(row['after_bytes_base64'])
    return target


def check_recorded_effects(data, targets, effects, resources):
    """Check saved complete target bytes even when a passive receipt is resealed."""
    from .write_guard_values import metadata
    from ..migration.plan_values import unb64
    expected = {}
    for row in data['result_artifacts']:
        identity = row['artifact']['id']
        paths = [r['path'] for r in resources if r['artifact_id'] == identity]
        require(len(paths) == 1, 'force_recorded_target_identity_unbound')
        expected[paths[0]] = metadata(jcs(row['artifact']))
    for op in data['operations']:
        kind = op['op']
        if kind in ('schema_migrate', 'merge_publish'):
            for row in op['changes']:
                expected[row['path']] = metadata(None if row['after_bytes_base64'] is None else unb64(row['after_bytes_base64']))
        elif kind == 'plan_edit':
            for row in op['sources']:
                expected[row['path']] = metadata(None if row['after'] is None else row['after'].encode('utf-8'))
        elif kind == 'representation_normalize':
            path = op['path']
            require(path in targets and targets[path]['sha256'] == op['target_byte_sha256'],
                'force_recorded_target_binding')
            expected[path] = targets[path]
        elif kind == 'baseline_create':
            from .baselines import object_documents
            for document in object_documents(op): expected[document.path] = metadata(document.content)
    require(set(effects) <= expected.keys(), 'force_unrequested_effect')
    require(all(targets.get(path) == bound for path, bound in expected.items()), 'force_recorded_target_binding')
