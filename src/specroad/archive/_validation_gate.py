"""Registration of real archived-byte checks in the common validation pipeline."""
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from .verification import verify_baseline_objects


def baseline_integrity_gate(objects):
    """Bind the real snapshot verifier to the common validation gate contract.

    The explicit host supplies actual immutable bytes, not a claimed success or
    cached report. Historical snapshot references need no current counterpart.
    Other required semantic/lifecycle gates remain independently mandatory.
    """
    from ._object_values import _objects
    from ..validation import ModelGate
    owned = tuple(_objects(objects).values())
    binding = canonical_json_sha256(sorted((item.reference.data for item in owned),
                                          key=lambda row: row['path']))

    def dependencies(context):
        return context.dependency_result({identity: [] for identity in context.subjects})

    def check(context):
        findings = []
        paths = {parse_json_object(d.content)['id']: d.path for d in context.documents}
        for identity in context.subjects:
            try:
                verify_baseline_objects(canonical_json_bytes(context.artifact(identity)), owned)
            except ModelError as error:
                findings.append({**error.diagnostic(), 'artifact_id': identity,
                    'path': paths[identity], 'object_path': error.path, 'severity': 'error'})
        return context.result(findings)

    return ModelGate('baseline_integrity', 'archived-baseline-integrity-v1',
                     dependencies, check, binding)
