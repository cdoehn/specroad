"""Concrete semantic operations, with native refusals retained as findings.

The fallback computes the explicitly requested operation on observed values.
It does not choose conflict resolutions, repair unrelated values, or fabricate
missing Evidence. Unreadable descriptions and ambiguous targets remain errors.
"""
from copy import deepcopy
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..model.errors import ModelError
from ..bundles.errors import BundleError
from ..model.paths import artifact_path
from ..changes.write_guard_values import require
from ..changes.force_domain_gates import record_denial
from ..changes.metadata_update import updated_audit_fields


def _observe(decisions, callback, intent):
    try:
        return callback()
    except (ModelError, BundleError) as error:
        record_denial(decisions, error, operation=intent['command_id'],
            subject=intent.get('target', intent.get('source', 'project')), requested=intent)
        return None


def compile_target(sources, intent, actor, time, decisions, *, services=None):
    name = intent['command_id']
    if name.startswith('plan.'):
        from .force_plan import target_plan
        return target_plan(sources, intent, actor, time, decisions)
    if name.startswith('proposal.'):
        from ..proposals.force import compile_target as proposal_target
        return proposal_target(sources, intent, actor, time, decisions, services=services)
    from .native_intents import compile_intent
    ops = None
    folded = None
    approval_gates = ()
    if sources.native is not None:
        ops = _observe(decisions, lambda: compile_intent(intent, sources.native, actor, time), intent)
    if ops is None:
        ops = explicit_operations(sources, intent, actor, time, decisions)
    if sources.native is not None:
        from .native_generic import _fold, _approval
        if len(ops) == 1:
            observed = _observe(decisions, lambda: _approval(sources.model, ops[0], actor, time, services), intent)
            if observed is not None:
                ops = [observed[0]]
                approval_gates = observed[1]
        folded = _observe(decisions, lambda: _fold(sources.model, ops, actor, time), intent)
        if folded is not None:
            from .native_qualification import publication_gates
            # Gate callbacks are executed by the normal native target assessor;
            # no callback is replaced with a positive surrogate.
            def examine():
                from ..changes.target import prepare_change_target
                from ..changes.target_model import _default_scope
                from .plans import _execution_inputs
                native = publication_gates(sources.native, folded, services=services)
                _, policy, special = _execution_inputs(sources.model, name, ops, actor, time, native)
                gates = tuple({g.gate_id: g for g in (*special, *native, *approval_gates)}.values())
                checked = prepare_change_target(sources.model, ops, policy=policy, gates=gates,
                    actor=actor, planned_at=time, change_plan_id='force-observation', request_id=None,
                    scope_descriptor=_default_scope(), metadata_policy_version='change-metadata-v1')
                checked.require_valid()
            _observe(decisions, examine, intent)
    if folded is not None:
        return {**sources.before, **folded.source_files}
    # Only a refused reducer needs the explicit byte projection.
    return apply_operations(sources, ops, actor, time, decisions, name)


def _guard(decisions, old, op, command):
    for name, actual in (('revision', old.get('revision')), ('sha256', digest(old))):
        key = 'expected_' + name
        if key in op and not (name == 'sha256' and op.get('op') == 'relation_remove'):
            decisions.decide(actual == op[key], gate_id='stale:' + key,
                diagnostic_code='CORE_CONFLICT', subject=old.get('id', 'artifact'), operation=command,
                observed_binding=actual, requested_binding=op[key], effect='execute_explicit_native_operation')


def apply_operations(sources, ops, actor, time, decisions, command):
    target = dict(sources.before)
    records = {key: (path, deepcopy(value)) for key, rows in sources.records.items()
        if len(rows) == 1 for path, value in rows}
    changed = set(); created = set()
    def current(identity):
        require(identity in records, 'force_target_missing_or_ambiguous', exit_code=3)
        return records[identity][1]
    def put(value):
        identity = value['id']
        require(identity not in sources.records, 'force_creation_identity_collision', exit_code=6)
        path = artifact_path(value['artifact_type'], identity, sources.configuration.id_prefix)
        records[identity] = (path, deepcopy(value)); changed.add(identity); created.add(identity)
    for op in ops:
        kind = op['op']
        if kind in ('create', 'evidence_record', 'relation_review_record', 'baseline_create', 'proposal_create'):
            field = {'create': 'artifact', 'evidence_record': 'evidence'}.get(kind, 'record')
            put(op[field])
            if kind == 'baseline_create':
                from ..changes.baselines import object_documents
                for document in object_documents(op):
                    target[document.path] = document.content
            if kind == 'relation_review_record':
                for withdrawal in op.get('approval_withdrawals', []):
                    identity = withdrawal['target']
                    value = current(identity); value['maturity'] = 'proposed'; changed.add(identity)
            continue
        identity = op.get('target') if kind not in ('relation_add', 'relation_remove') else op['source']
        old = deepcopy(current(identity)); value = current(identity)
        _guard(decisions, old, op, command)
        if kind == 'update':
            from ..changes.json_patch import JsonPatch, _apply_one
            program = JsonPatch(op['patch']).data
            for index, item in enumerate(program):
                if item['op'] == 'test':
                    _observe(decisions, lambda: _apply_one(value, item, index), {'command_id': command, **op})
                else:
                    value = _apply_one(value, item, index)
            require(type(value) is dict, 'force_native_artifact_object_required', exit_code=2)
            records[identity] = (records[identity][0], value)
        elif kind in ('transition', 'retire'):
            requested = 'retired' if kind == 'retire' else op['to']
            if 'from' in op:
                decisions.decide(value.get('maturity') == op['from'], gate_id='stale:lifecycle_source',
                    diagnostic_code='CORE_CONFLICT', subject=identity, operation=command,
                    observed_binding=value.get('maturity'), requested_binding=op['from'],
                    effect='set_explicit_lifecycle_label_without_approval')
            value['maturity'] = requested
        elif kind == 'relation_add':
            value['relations'] = [*value['relations'], deepcopy(op['relation'])]
        elif kind == 'relation_remove':
            matches = [v for v in value['relations'] if v.get('relation_id') == op['relation_id']]
            require(len(matches) == 1, 'force_relation_missing_or_ambiguous', exit_code=3)
            decisions.decide(digest(matches[0]) == op['expected_sha256'], gate_id='hash:relation_source',
                diagnostic_code='CORE_CONFLICT', subject=op['relation_id'], operation=command,
                observed_binding=digest(matches[0]), requested_binding=op['expected_sha256'],
                effect='remove_explicit_observed_relation')
            value['relations'] = [v for v in value['relations'] if v is not matches[0]]
        elif kind == 'proposal_change':
            value = deepcopy(op['record']); records[identity] = (records[identity][0], value)
        else:
            require(False, 'force_native_operation_unavailable', exit_code=2)
        if value != old:
            changed.add(identity)
    for identity in sorted(changed):
        path, value = records[identity]
        if identity not in created:
            original = sources.artifact(identity)[1]
            value.update(updated_audit_fields(original, actor=actor, planned_at=time))
        target[path] = jcs(value)
    return target


def explicit_operations(sources, intent, actor, time, decisions):
    name = intent['command_id']; data = {k: v for k, v in intent.items() if k != 'command_id'}
    from ..model.authoring_command_ids import BASIC_COMMANDS
    from .native_specialists import FIELDS, KINDS
    allowed = {'artifact.create': {'artifact_type', 'fields'},
        'artifact.update': {'target', 'patch', 'options', 'expected_revision', 'expected_sha256'},
        'lifecycle.transition': {'target', 'to', 'reason', 'expected_revision', 'expected_sha256'},
        'relation.add': {'source', 'type', 'target', 'rationale', 'position'},
        'relation.remove': {'source', 'relation_id', 'expected_sha256', 'reason'}, **FIELDS}
    require(name in allowed and not data.keys() - allowed[name], 'invalid_authoring_intent', exit_code=2)
    try:
        return _explicit(sources, name, data, actor, time, decisions)
    except KeyError as error:
        from ..changes.request_ids import AuthoringError
        raise AuthoringError('missing_authoring_input', exit_code=2) from error


def _explicit(sources, name, data, actor, time, decisions):
    from .native_specialists import KINDS
    from ..model.audit import new_artifact_audit, actor as read_actor
    from ..model.audit_values import UtcTimestamp
    def audit():
        return new_artifact_audit(actor=read_actor(actor), planned_at=UtcTimestamp(time)).as_fields()
    def add(source, kind, target, fields):
        edge = dict(type=kind, target=target, external_identities=[], extensions={},
            **sources.relation().as_fields(), created_at=time, created_by=actor)
        edge.update({k: fields[k] for k in ('rationale', 'position') if k in fields})
        return dict(op='relation_add', source=source, relation=edge)
    if name == 'artifact.create' or name in KINDS:
        from ..model.authoring_command_ids import CREATE_KINDS
        from ..model.versions import SCHEMA_VERSION
        kind = data['artifact_type'] if name == 'artifact.create' else KINDS[name]
        require(kind in CREATE_KINDS and type(data['fields']) is dict, 'force_creation_input_required', exit_code=2)
        identity = sources.allocate(kind)
        fields = deepcopy(data['fields']); fields.setdefault('relations', []); fields.setdefault('extensions', {})
        if kind == 'requirement':
            fields.setdefault('implementation_status', 'not_started'); fields.setdefault('verification_plan_status', 'not_planned')
            default = sources.configuration.data.get('language_policy', {}).get('default_language')
            if default is not None: fields.setdefault('language', default)
        value = dict(schema_version=SCHEMA_VERSION, artifact_type=kind, id=identity.id,
            id_scheme=identity.id_scheme, maturity='draft', **audit())
        # Explicit content fields keep their actual value, including invalid values.
        # Identity/audit generation remains the command's defined operation.
        protected = set(value) & fields.keys()
        require(not protected, 'force_creation_identity_audit_is_generated', exit_code=2)
        value.update(fields)
        result = [dict(op='create', artifact=value, result_id=value['id'])]
        if name in ('section.add', 'block.add'):
            result.append(add(data['parent_id'], 'contains', value['id'], data))
        return result
    if name in ('artifact.update', 'block.update'):
        require(('patch' in data) != ('options' in data), 'exactly_one_update_input_required', exit_code=2)
        value = sources.artifact(data['target'])[1]
        if 'options' in data:
            from ..changes.field_patches import compile_field_patch
            patch = compile_field_patch(value, data['options']).data
        else:
            patch = data['patch']
        return [dict(op='update', target=data['target'], patch=patch,
            **{k: data[k] for k in ('expected_revision', 'expected_sha256') if k in data})]
    if name in ('lifecycle.transition', 'block.remove'):
        value = sources.artifact(data['target'])[1]
        return [dict(op='transition', target=data['target'], to=data.get('to', 'retired'),
            **{'from': value.get('maturity')}, metadata={'reason': data['reason']},
            **{k: data[k] for k in ('expected_revision', 'expected_sha256') if k in data})]
    if name == 'relation.add':
        return [add(data['source'], data['type'], data['target'], data)]
    if name == 'relation.remove':
        return [dict(op='relation_remove', **data)]
    if name == 'section.move':
        incoming = [(key, edge) for key, rows in sources.records.items() if len(rows) == 1
            for edge in rows[0][1].get('relations', [])
            if edge.get('type') == 'contains' and edge.get('target') == data['target']]
        require(len(incoming) == 1, 'force_section_parent_ambiguous', exit_code=3)
        owner, edge = incoming[0]
        return [dict(op='relation_remove', source=owner, relation_id=edge['relation_id'],
            expected_sha256=data['expected_relation_sha256'], reason=data['reason']),
            add(data['parent_id'], 'contains', data['target'], data)]
    if name == 'evidence.record':
        require(type(data['record']) is dict, 'explicit_recorded_evidence_required', exit_code=2)
        return [dict(op='evidence_record', evidence=deepcopy(data['record']), verification_id=data['verification_id'],
            **({'configuration_id': data['configuration_id']} if 'configuration_id' in data else {}))]
    if name == 'relation.review':
        from .force_reviews import record
        return [record(sources, data, actor, time, decisions)]
    if name == 'section.remove':
        from .force_sections import remove
        return remove(sources, data, actor, time)
    from .force_specialists import compile_specialist
    return compile_specialist(sources, name, data, actor, time, decisions)
