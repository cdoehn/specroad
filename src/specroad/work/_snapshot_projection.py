"""Pure logical input projections, independent of source roots and live guards."""

import json

from ..model.canonical import canonical_json_bytes


def captured_input_manifest(entries):
    value = {'format_version': 'captured-inputs-v1', 'inputs': [
        {key: entry[key] for key in ('root_id', 'path', 'size', 'sha256')}
        for entry in entries]}
    return canonical_json_bytes(value)


def capture_progress(*, phase, expected_inputs, entries, confirmed_units,
                     captured_bytes, validated_inputs, revalidated_inputs,
                     validation_bytes, error, closed, complete,
                     input_manifest_sha256):
    # The caller supplies only data, never source boundaries or live handles.
    value = {'format_version': 'input-capture-progress-v1', 'phase': phase,
        'expected_inputs': expected_inputs, 'enumerated_inputs': len(entries),
        'completed_inputs': sum(entry['complete'] for entry in entries),
        'confirmed_units': confirmed_units, 'captured_bytes': captured_bytes,
        'validated_inputs': validated_inputs, 'revalidated_inputs': revalidated_inputs,
        'validation_bytes': validation_bytes,
        'inputs': entries, 'error': error, 'closed': closed,
        'complete': complete,
        'input_manifest_sha256': input_manifest_sha256, 'model_root_sha256': None,
        'atomic_project_snapshot': False, 'durable_checkpoint': False,
        'continuation_scope': 'current_invocation'}
    return json.loads(canonical_json_bytes(value))
