"""Read-only proof of a later successful Apply for an explicitly blocked claim."""
import hashlib
from .errors import ControlError
from .local import read_private, decode_object


def recover_blocked(engine, ledger, source, protocol, protocol_path):
    """Adopt proven later output, never repeat the completed blocked turn."""
    content = read_private(protocol_path)
    try:
        if decode_object(content) != protocol:
            raise ValueError
    except (ValueError, UnicodeError):
        raise ControlError("recovery_evidence_changed", "The completion evidence changed during recovery.") from None
    answer = protocol.get("answer")
    required = {"source_result_sha256", "status", "patch_sha256", "message"}
    if (not isinstance(answer, dict) or set(answer) != required
            or not all(isinstance(value, str) for value in answer.values())
            or answer["source_result_sha256"] != source["sha256"]
            or answer["status"] != "blocked" or answer["patch_sha256"] != ""):
        raise ControlError("recovery_evidence_invalid", "The blocked receipt does not match the claimed source.")
    patch, result = _blocked_output(engine, ledger, source)
    engine.codex.check()  # Recheck inactivity after package inspection, without a turn.
    current_source = engine.exchange.source(source)
    current_patch, current_result = _blocked_output(engine, ledger, current_source)
    if (current_patch["sha256"] != patch["sha256"]
            or current_result["sha256"] != result["sha256"]
            or read_private(protocol_path) != content):
        raise ControlError("recovery_evidence_changed", "Recovery inputs changed; the claim remains blocked.")
    ledger.adopt_blocked(patch["sha256"], result, hashlib.sha256(content).hexdigest())


def _blocked_output(engine, ledger, source):
    patches = engine.eligible_patches(source)
    if len(patches) != 1:
        raise ControlError("recovery_unproven", "Blocked recovery requires exactly one bound patch.")
    patch = patches[0]
    results = engine.exchange.following(source, patch["sha256"])
    if len(results) != 1:
        raise ControlError("recovery_unproven", "Blocked recovery requires exactly one bound Apply result.")
    result = results[0]
    if (result["success"] is not True or result["primary_kind"] != "success"
            or result["entrypoint_started"] is not True or result["dirty"] is not False
            or result["completed_commit"] != result["binding"]["base_commit"]
            or result["run_id"] in ledger.known_runs()):
        raise ControlError("recovery_unproven", "The bound Apply is not a new clean committed success.")
    return patch, result
