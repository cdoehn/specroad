"""Local schema resources for implemented output contracts, not approval gates.

The typed producers retain cross-field/semantic and publication-integrity checks.
Schemas cover their serialized field shapes; arbitrary result, project, environment
or schema-document objects stay passive JSON data. No remote resolution exists.
"""
from ..model._schema import validate_builtin
from ..model.schema_identity import CATEGORIES, DIALECT, ENVELOPE_ID, RESULT_IDS
from .results import FORMAT_VERSION, ResultStatus
from ..diagnostics import diagnostic_schema


def _object(properties, required=None, extra=False):
    return {"type": "object", "properties": properties,
            "required": sorted(properties if required is None else required), "additionalProperties": extra}


def _array(schema):
    return {"type": "array", "items": schema}


def _nullable(schema):
    return {"anyOf": [{"type": "null"}, schema]}


def _with_currentness(schema, *, comparison=False):
    """Optional native read observation; legacy payloads keep their contract."""
    text = {'type': 'string'}
    sha = {'type': 'string', 'pattern': r'^[0-9a-f]{64}(?![\s\S])'}
    observation = _object({
        'format_version': {'const': 'currentness-read-input-v1'},
        'validation_scope': {'const': 'supplied_model_and_native_observations'},
        'project_id': text, 'input_sha256': sha, 'project_configuration_sha256': sha,
        'record_bindings': _array(_object({'id': text, 'sha256': sha})),
        'verification_summary': {'type': 'object'}, 'coverage': {'type': 'object'},
        'coverage_sha256': sha, 'code_states': _array({'type': 'object'}),
        'relation_reviews': {'type': 'object'},
        'review_groups': _object({state: _object({'relation_ids': _array(text), 'affected_ids': _array(text)})
                                 for state in ('current', 'unreviewed', 'suspect', 'invalid')}),
        **{name: {'const': False} for name in ('project_files_verified', 'atomic_snapshot',
            'external_run_verified', 'release_readiness_evaluated', 'source_code_executed',
            'write_authorized', 'approval_granted')}})
    bound = _object({'sha256': sha, 'observation': observation})
    schema['properties']['currentness'] = (_object({'before': bound, 'after': bound,
        'changed': {'type': 'boolean'}}) if comparison else bound)
    if comparison:
        schema['properties']['currentness_inputs'] = _object({'before_sha256': sha, 'after_sha256': sha})
        schema['properties']['evidence_currency'] = {'anyOf': [
            _object({'state': {'const': 'not_evaluated'}}),
            _object({'state': {'const': 'compared'}, 'before_sha256': sha, 'after_sha256': sha})]}
    return schema


def _fields(schema_id):
    text = {"type": "string"}; nonempty = {"type": "string", "minLength": 1}
    obj = {"type": "object"}; boolean = {"type": "boolean"}
    count = {"type": "integer", "minimum": 0}
    strings = _array(text)
    sha = {"type": "string", "pattern": r"^[0-9a-f]{64}(?![\s\S])"}
    diagnostic = diagnostic_schema()
    reference = _object({"path": nonempty, "media_type": nonempty, "size": count,
                         "sha256": sha, "result_schema": nonempty})
    surface = {"command_id": nonempty, "words": strings, "aliases": _array(strings),
               "command_class": nonempty, "preflight_profile": nonempty}
    runtime = _object({name: text for name in ("implementation", "python_version", "system", "machine")})
    support = _object({"minimum_minor": text, "declared_minors": strings, "maximum_declared_minor": text,
        "tested_minors": strings, "maximum_tested_minor": _nullable(text), "fully_verified_minors": strings,
        "verification_status": text, "evidence_refs": _array(True)})
    distribution = {"distribution_kind": text, "build_id": _nullable(text), "build_sha256": _nullable(sha),
                    "build_hash_scope": _nullable(text)}
    entry = _object({"schema_id": nonempty, "version": nonempty, "stability": {"enum": ["experimental"]},
        "category": {"enum": list(CATEGORIES)}, "validation_scope": nonempty, "sha256": sha})
    work = _object({"continuation_supported": {"const": False},
        "external_side_effects": {"const": []}, "checkpoint_algorithms": {"const": []},
        "minimum_step": _object({"kind": nonempty, "required_inputs": strings,
            "limits": _object({"memory_bytes": {"type": "null"}, "cpu_seconds": {"type": "null"}}),
            "limits_status": {"const": "unmeasured"}, "on_blocked": {"const": "fail_without_checkpoint"},
            "blocked_exit_code": {"const": 5}})})
    bound = _object({"state": {"enum": ["known", "unknown", "unlimited"]}, "value": _nullable(count)})
    process_limit = _object({"scope": {"const": "process"}, "unit": text, "source": text,
                            "soft": bound, "hard": bound})
    limits = _object({"process_address_space_bytes": process_limit, "process_cpu_seconds": process_limit,
        "host_memory_bytes": {"type": "null"}, "host_cpu_quota": {"type": "null"},
        "host_limits_status": {"const": "unknown"}, "scope": {"const": "process_limits_not_host_capacity"}})
    if schema_id == ENVELOPE_ID:
        return _object({"format_version": {"const": FORMAT_VERSION}, "command": nonempty,
            "status": {"enum": [s.value for s in ResultStatus]}, "project": _nullable(obj),
            "result": True, "result_ref": _nullable(reference), "diagnostics": _array(diagnostic),
            "summary": _object({"complete": boolean}, extra=True)})
    if schema_id == "help-v1":
        return _object({"usage": text, "options": _array(_object({"flag": text, "values": strings}, ("flag",))),
            "commands": _array(_object({k: surface[k] for k in ("command_id", "words", "aliases")})),
            "exit_codes": {"type": "object", "additionalProperties": text}, "examples": strings, "scope": text})
    if schema_id == 'document-work-v1':
        return _object({'format_version': {'const': 'document-work-v1'},
            'input_manifest_sha256': sha, 'task_manifest_sha256': sha,
            'source_scope': {'const': 'explicit_saved_model'}, 'project_files_verified': {'const': False},
            'composition': obj, 'blocks': _array(_object({'artifact_id': nonempty, 'observation': obj}))})
    if schema_id == 'work-evaluation-v1':
        return _object({'format_version': {'const': 'work-evaluation-v1'},
            'input_manifest_sha256': sha, 'task_manifest_sha256': sha,
            'source_scope': {'const': 'explicit_saved_model'}, 'project_files_verified': {'const': False},
            'results': _array(_object({'key': nonempty, 'kind': {'enum': ['validate', 'srx']},
                'observation': obj, 'exit_code': {'enum': [0, 1]}}))})
    if schema_id == 'project-init-v1':
        return _object({'format_version': {'const': 'project-init-v1'},
            'project_root': nonempty, 'project_id': nonempty, 'primary_document_id': nonempty,
            'files': _array(_object({'path': nonempty, 'size': count, 'sha256': sha})),
            'directories': strings, 'bootstrap_state': {'const': 'complete'},
            'validation_scope': {'const': 'configuration_record_fields_and_distribution_bindings'},
            'full_semantic_validation': {'const': False}})
    if schema_id == 'project-inspect-v1':
        return _object({'format_version': {'const': '1.0.0'},
            'semantic': _object({'project_id': _nullable(nonempty), 'model_root_sha256': _nullable(sha),
                'schema_version': _nullable(nonempty),
                'active_profiles': _nullable(_array(_object({'profile_id': nonempty, 'version': nonempty}))),
                'artifact_counts': _nullable({'type': 'object', 'additionalProperties': count}),
                'migration_needed': _nullable(boolean),
                'diagnostic_summary': _nullable(_object({s: count for s in ('error', 'warning', 'info')})),
                'primary_documents': _nullable(_array(_object({'id': nonempty, 'title': nonempty})))}),
            'runtime': _object({'project_root': _nullable(nonempty), 'open_transaction': _nullable(obj),
                'writer_lock': _nullable(obj), 'consistency_state': {'enum':
                    ['consistent', 'recovery_required', 'writer_active', 'unknown']}})})
    if schema_id == 'artifact-show-v1':
        def relation_view(inverse):
            return _object({'relation_id': nonempty, 'type': nonempty, 'source': nonempty,
                'target': nonempty, 'inverse': {'const': inverse}, 'stored_source': nonempty,
                'stored_relation': _object({'relation_id': nonempty, 'type': nonempty,
                                           'target': nonempty}, extra=True)})
        return _object({'format_version': {'const': '1.0.0'}, 'artifact': obj,
            'incoming': _array(relation_view(True)), 'outgoing': _array(relation_view(False)),
            'coverage': _object({'scope': {'const': 'current_project_artifacts'},
                'source_count': count, 'relation_count': count, 'observation_sha256': sha,
                'validation_scope': {'const': 'relation_references_and_canonical_storage_only'},
                'atomic_snapshot': {'const': False}})})
    if schema_id == 'artifact-trace-v1':
        edge = _object({'relation_id': nonempty, 'type': nonempty, 'source': nonempty,
            'target': nonempty, 'inverse': boolean, 'stored_source': nonempty,
            'stored_relation': _object({'relation_id': nonempty, 'type': nonempty,
                                       'target': nonempty}, extra=True)})
        return _with_currentness(_object({'format_version': {'const': '1.0.0'}, 'start': nonempty,
            'direction': {'enum': ['in', 'out', 'both']}, 'depth': count,
            'nodes': _array(_object({'id': nonempty, 'artifact_type': nonempty, 'distance': count})),
            'edges': _array(edge), 'coverage': _object({'scope': {'const': 'current_project_artifacts'},
                'source_count': count, 'relation_count': count, 'observation_sha256': sha,
                'validation_scope': {'const': 'relation_references_and_canonical_storage_only'},
                'atomic_snapshot': {'const': False}})}))
    if schema_id == 'artifact-why-v1':
        identity = _object({'id': nonempty, 'id_scheme': nonempty, 'artifact_type': nonempty, 'id_prefix': nonempty})
        path = _object({'artifacts': _array(identity),
                        'relations': _array(_object({'relation_id': nonempty, 'id_scheme': nonempty})),
                        'inverse': _array(boolean)})
        return _object({'format_version': {'const': '1.0.0'}, 'start': nonempty, 'depth': count,
            'traversal': {'const': 'stored_direction_with_symmetric_inverses'},
            'targets': _array(_object({'id': nonempty, 'artifact_type': {'enum': ['goal', 'need', 'source']},
                                      'distance': count, 'path_count': count})),
            'paths': _array(path), 'path_count': count,
            'coverage': _object({'scope': {'const': 'current_project_artifacts'},
                'source_count': count, 'relation_count': count, 'observation_sha256': sha,
                'validation_scope': {'const': 'relation_references_canonical_storage_and_hierarchies_only'},
                'atomic_snapshot': {'const': False}})})
    if schema_id == 'configuration-evaluation-v1':
        identity = _object({'id': nonempty, 'id_scheme': nonempty, 'artifact_type': nonempty, 'id_prefix': nonempty})
        path = _object({'artifacts': _array(identity),
                       'relations': _array(_object({'relation_id': nonempty, 'id_scheme': nonempty})),
                       'inverse': _array({'const': False})})
        return _object({'format_version': {'const': '1.0.0'},
            'configuration': _object({'configuration_id': nonempty,
                'configuration_revision': {'type': 'integer', 'minimum': 1},
                'name': nonempty, 'dimensions': _array(obj), 'effective_values': obj, 'sha256': sha}),
            'applicable_artifact_ids': strings, 'excluded_artifact_ids': strings,
            'evaluations': _array(_object({'artifact_id': nonempty,
                'status': {'enum': ['applicable', 'excluded']},
                'reason': {'enum': ['unconditional', 'condition_true', 'condition_false']}})),
            'inconsistent_dependencies': _array(_object({'source_id': nonempty, 'target_id': nonempty,
                'distance': {'type': 'integer', 'minimum': 1}, 'path': path})),
            'consistent': boolean, 'dependency_scope': {'const': 'stored_strong_relations'},
            'source_count': count, 'relation_count': count})
    if schema_id == 'artifact-impact-v1':
        observed_field = {'anyOf': [
            _object({'state': {'const': 'present'}, 'value': nonempty}),
            _object({'state': {'enum': ['missing', 'unavailable']}})]}
        observation = _object({'artifact_id': nonempty, 'present': boolean,
            'artifact_type': _nullable(nonempty),
            'fields': _object({name: observed_field for name in ('priority', 'verification_plan_status')}),
            'verification_assessment': _object({'state': {'const': 'not_performed'}})})
        connection = _object({'relation_id': nonempty, 'source_id': nonempty, 'target_id': nonempty,
            'related_id': nonempty, 'direction': {'enum': ['incoming', 'outgoing']},
            'related_present': boolean, 'review_status': {'enum': ['unreviewed', 'current', 'suspect', 'invalid']},
            'review_reason': _nullable(nonempty), 'selected_review_id': _nullable(nonempty),
            'matching_review_ids': strings, 'historical_review_ids': strings})
        return _with_currentness(_object({'format_version': {'const': '1.1.0'}, 'artifact_id': nonempty,
            'depth': {'const': 1}, 'transitive': {'const': False},
            'artifact_observations': _array(observation),
            'groups': _array(_object({'relation_type': nonempty, 'artifact_ids': strings,
                                      'connections': _array(connection)})),
            'review_groups': _object({state: _object({'relation_ids': strings, 'affected_ids': strings})
                                     for state in ('unreviewed', 'current', 'suspect', 'invalid')}),
            'coverage': _object({'scope': {'const': 'current_project_artifacts'},
                'source_count': count, 'relation_count': count, 'review_record_count': count,
                'observation_sha256': sha,
                'validation_scope': {'const': 'artifact_fields_and_relation_review_status_only'},
                'atomic_snapshot': {'const': False}})}))
    if schema_id == 'artifact-query-v1':
        return _object({'items': _array(_object({'id': nonempty, 'artifact_type': nonempty}, extra=True)),
            'total': count, 'offset': count, 'limit': count, 'returned': count, 'truncated': boolean})
    if schema_id == 'artifact-diff-v1':
        pair = _object({'before_sha256': sha, 'after_sha256': sha})
        return _with_currentness(_object({'comparison_version': {'const': 'semantic-diff-v1'},
            'project_id': nonempty, 'input_sha256': sha,
            'before_artifacts_sha256': sha, 'after_artifacts_sha256': sha,
            'configuration_inputs': pair, 'timing_bounds': obj,
            'changed': boolean, 'categories': strings, 'changes': _array(obj),
            'project_configuration': _object({'state': {'const': 'compared'}, 'changed': boolean,
                'fields': _array(obj), 'before_sha256': sha, 'after_sha256': sha}),
            'timing': _array(obj), 'inventory_delta': _object({'scope': {'const': 'supplied_artifact_sets'},
                'added_ids': strings, 'removed_ids': strings}),
            'configuration_scope': {'anyOf': [
                _object({'state': {'const': 'not_evaluated'}}),
                _object({'state': {'const': 'evaluated'},
                    'scope': {'const': 'supplied_artifact_applicability'},
                    'before': _fields('configuration-evaluation-v1'),
                    'after': _fields('configuration-evaluation-v1'),
                    'added_ids': strings, 'removed_ids': strings, 'retained_ids': strings,
                    'membership_changed': boolean, 'configuration_changed': boolean})]},
            'evidence_currency': _object({'state': {'const': 'not_evaluated'}}),
            'validation_scope': {'const': 'supplied_artifact_fields_and_declared_semantics_only'},
            'full_semantic_validation': {'const': False}, 'approval_granted': {'const': False},
            'write_authorized': {'const': False}}), comparison=True)
    if schema_id == "version-info-v1":
        return _object({"version_info_format_version": {"const": "1.0.0"}, "program_version": text,
            **distribution, "build_hash_algorithm": _nullable(text), "release_approved": boolean,
            "build_identity_status": text, "runtime": runtime, "python_support": support, "supported_schema_versions": strings,
            "supported_output_format_versions": {"type": "object", "additionalProperties": strings}})
    if schema_id == "command-description-v1":
        return _object({"format_version": {"const": "1.0.0"}, **surface, "budget_policy_version": _nullable(text),
            "lock_kind": {"enum": ['none', 'bootstrap']}, "work": work,
            "parameters": _array(_object({"name": text, "kind": {"const": "positional"},
                "datatype": text, "required": boolean, "choices": strings})),
            "options": _array(_object({"flag": text, "datatype": text, "repeatable": boolean,
                "required": boolean, "choices": strings, "excludes": strings})),
            "mutually_exclusive": _array(strings),
            "stdin": _object({"mode": {"const": "unused"}, "explicit_markers": {"const": []}}),
            "stdout": _object({"formats": strings, "default_format": text,
                "json_envelope_version": {"const": FORMAT_VERSION}, "result_schema": nonempty,
                "continuation": _object({"supported": {"const": False}, "sarif_fallback": {"type": "null"}})}),
            "diagnostic_codes": strings, "exit_codes": _array({"type": "integer", "minimum": 0, "maximum": 8}),
            "write_effects": _object({"scope": text, "required_write_paths": strings, "external_work": strings}),
            "requires_project": boolean, "requires_git": boolean,
            "request_schema": obj, "examples": _array(obj)})
    if schema_id == "capabilities-v1":
        semantic = _object({"program_version": text, "distribution": _object(distribution),
            "capability_ids": strings, "commands": _array(_object({**surface, "output_formats": strings,
                "result_schema": text, "continuation_supported": boolean})),
            "command_groups": strings, "command_classes": strings, "output_formats": strings, "exchange_formats": strings,
            "supported_versions": {"type": "object", "additionalProperties": strings},
            "python_support": support, "work": _object({"engine_available": {"const": False},
                "checkpoint_algorithms": {"const": []}, "budget_policy_version": {"type": "null"}})})
        return _object({"format_version": {"const": "1.0.0"}, "semantic": semantic,
            "runtime": _object({"interpreter": runtime, "limits": limits})})
    if schema_id == "schema-catalog-v1":
        return _object({"format_version": {"const": "1.0.0"}, "schemas": _array(entry),
                "categories": _object({name: count for name in CATEGORIES})})
    if schema_id == 'environment-v1':
        observation = {'anyOf': [_object({'value': value, 'unit': nonempty, 'source': nonempty,
            'state': {'const': state}, 'scope': nonempty})
            for state, value in (('observed', count), ('unknown', {'type': 'null'}))]}
        environment_python = _object({'implementation': nonempty, 'python_version': nonempty,
            'supported': boolean, 'system': text, 'machine': text, 'support': support},
            ('implementation', 'python_version', 'supported'))
        environment_distribution = _object({
            'distribution_kind': {'enum': ['module', 'zipapp', 'unknown']},
            'build_id': _nullable(nonempty), 'build_sha256': _nullable(sha),
            'build_identity_status': {'enum': ['recorded', 'unrecorded', 'unavailable']},
            'release_approved': boolean})
        check = _object({'check_id': nonempty, 'required': boolean,
            'state': {'enum': ['passed', 'failed', 'unknown', 'not_applicable']}, 'reason': nonempty,
            'exit_code': {'type': 'integer', 'minimum': 0, 'maximum': 7}})
        budget = _object({'value': count, 'unit': nonempty, 'origin': nonempty,
                          'limit_class': {'const': 'soft_work_target'}})
        return _object({'environment_format_version': {'const': '1.0.0'},
            'compatible': _nullable(boolean),
            'operation_readiness': {'enum': ['not_requested', 'ready', 'blocked', 'unknown']},
            'python': environment_python, 'distribution': environment_distribution, 'checks': _array(check),
            'recovery_required': _nullable(boolean),
            'resource_policy': _object({'policy_version': {'const': 'runtime-budget-v2'},
                'profile': {'enum': ['constrained', 'standard']}, 'profile_source': {'enum': ['default', 'cli']},
                'scope': {'const': 'declared_soft_work_targets'}, 'budget_engine_available': {'const': False},
                'effective_budgets': {'type': 'object', 'additionalProperties': budget},
                'classified_limits': _object({
                    'soft_work_target': obj, 'semantic_scope': obj, 'hard_safety_or_format': obj,
                    'observed_host_limit': {'type': 'object', 'additionalProperties': observation}})}),
            'observations': _object({name: observation for name in ('cpu_capacity', 'memory_limit', 'storage_capacity')}),
            'semantic_validation_performed': {'const': False}, 'target_command_id': _nullable(nonempty),
            'metadata': _nullable(obj)})
    if schema_id == "schema-document-v1":
        return _object({"format_version": {"const": "1.0.0"}, "metadata": entry,
            "schema": _object({"$schema": {"const": DIALECT}, "$id": nonempty}, extra=True)})
    if schema_id == "sarif-specroad-v1":
        # Local emitted subset, not the complete third-party SARIF metaschema.
        return _object({"version": {"const": "2.1.0"}, "$schema": text, "runs": _array(_object({
            "tool": _object({"driver": _object({"name": text, "version": text})}),
            "invocations": _array(_object({"executionSuccessful": boolean, "exitCode": count})),
            "results": _array(_object({"ruleId": text, "level": {"enum": ["note", "warning", "error"]},
                "message": _object({"text": text}), "properties": _object({"specroad": diagnostic}),
                "locations": _array(obj)}, ("ruleId", "level", "message", "properties"))),
            "properties": _object({"specroad": obj})}))})
    raise ValueError("Unknown local result schema")


def result_json_schema(schema_id):
    if type(schema_id) is not str or schema_id not in RESULT_IDS:
        raise ValueError("Unknown local result schema")
    return {"$schema": DIALECT, "$id": schema_id,
        "description": "Implemented serialized field contract; producer invariants and bound file integrity are additional checks.",
        "x-specroad-validation-scope": "sarif_projection_only" if schema_id == "sarif-specroad-v1" else "result_fields_only",
        **_fields(schema_id)}


def validate_result_document(schema_id, value):
    validate_builtin(value, result_json_schema(schema_id))
