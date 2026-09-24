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
    if schema_id == "version-info-v1":
        return _object({"version_info_format_version": {"const": "1.0.0"}, "program_version": text,
            **distribution, "build_hash_algorithm": _nullable(text), "release_approved": boolean,
            "build_identity_status": text, "runtime": runtime, "python_support": support, "supported_schema_versions": strings,
            "supported_output_format_versions": {"type": "object", "additionalProperties": strings}})
    if schema_id == "command-description-v1":
        return _object({"format_version": {"const": "1.0.0"}, **surface, "budget_policy_version": _nullable(text),
            "lock_kind": {"const": "none"}, "work": work,
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
