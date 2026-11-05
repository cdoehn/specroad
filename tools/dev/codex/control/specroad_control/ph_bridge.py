"""Read-only bridge, run with the EXISTING PatchHarbor Python and -I.

No imports from a Result runtime, no apply/bundle/configure/registration calls.
The internal Result reader is a reviewed compatibility seam for Core 1.2.1;
an unavailable seam fails closed rather than approximating snapshot validation.
"""
import json
from hashlib import sha256
import io
import zipfile
from pathlib import Path
import sys


def binding(context):
    return {"repo_id": str(context.repo_id), "base_commit": str(context.base_commit),
            "state_fingerprint": context.state_fingerprint,
            "fingerprint_algorithm": context.fingerprint_algorithm}


def development_capability(path, expected_sha):
    from specroad_control.mixed_contract import CAPABILITY_PATH, capability
    from specroad_control.local import decode_object
    if path.stat().st_size > 512 * 1024 * 1024:
        raise ValueError
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != expected_sha:
        raise ValueError
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = [e for e in archive.infolist() if e.filename == 'base/' + CAPABILITY_PATH]
        if not entries:
            return None
        if len(entries) != 1 or entries[0].file_size > 4096:
            raise ValueError
        return capability(decode_object(archive.read(entries[0])))


def main():
    from patchharbor import api
    from patchharbor.result_reader import capture_result_reference
    from patchharbor.errors import PatchHarborError
    try:
        operation, raw = sys.argv[1:3]
        path = Path(raw)
        if operation == "result":
            captured = capture_result_reference(path)
            facts = captured.facts
            primary = facts.primary_result
            data = {"kind": "result", "sha256": captured.sha256,
                    "binding": binding(facts.context), "run_id": facts.run_id,
                    "repository_path": facts.context.repository_path,
                    "operation": facts.operation, "dry_run": facts.dry_run,
                    "success": primary.success, "primary_kind": primary.kind.value,
                    "entrypoint_started": primary.entrypoint_started,
                    "patch_sha256": facts.patch_sha256,
                    "expected": None if facts.expected is None else binding(facts.expected),
                    "completed_commit": None if facts.completed_commit is None else str(facts.completed_commit),
                    "dirty": facts.context.dirty, "captured_at": None if captured.handoff is None else json.loads(captured.handoff.environment).get("captured_at")}
            installed = development_capability(path, captured.sha256)
            if installed is not None:
                data['development_contract'] = installed
        elif operation == "current":
            from patchharbor.repository_state import capture_repository_context
            captured = capture_result_reference(path)
            context = capture_repository_context(Path(captured.facts.context.repository_path), read_only=True)
            data = {"kind": "current", "sha256": captured.sha256, "binding": binding(context),
                    "repository_path": str(context.repository_path), "dirty": context.dirty}
        elif operation == "patch":
            info = api.inspect_patch(path)
            data = {"kind": "patch", "sha256": info.package_sha256, "binding": binding(info.manifest)}
        elif operation == "validate":
            report = api.validate_patch(path, reference_bundle=Path(sys.argv[3]))
            data = {"kind": "patch", "sha256": report.inspection.package_sha256,
                    "binding": binding(report.inspection.manifest), "reference_sha256": report.reference_sha256,
                    "binding_matches": report.binding_matches}
        else:
            raise ValueError
        print(json.dumps({"ok": True, "data": data}))
        return 0
    except (PatchHarborError, OSError, ValueError, TypeError, IndexError, zipfile.BadZipFile):
        print(json.dumps({"ok": False, "error": "core_rejected"}))
        return 1


if __name__ == "__main__":
    # -I starts this file without its package parent on the import path.
    # Library callers already imported the package; never mutate their path.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    try:
        raise SystemExit(main())
    except ImportError:
        print(json.dumps({"ok": False, "error": "core_unavailable"}))
        raise SystemExit(1)
