"""Concrete original-byte projects and independent Force observations."""
import base64
import json
from hashlib import sha256
from specroad.changes import prepare_resource_plan
from specroad.force import ForceRequest
from specroad.model.paths import artifact_path
from support.native_plan_authoring import setup, files, values, ACTOR, ALLOW


def fixture(root):
    setup(root, with_plan=False)
    goal = next(v for v in values(root).values() if v['artifact_type'] == 'goal')
    return root, artifact_path('goal', goal['id'], 'SR')


def replacement(root, path, raw, *, reason=None, request_id='force-request', expected=None):
    before = (root/path).read_bytes() if (root/path).exists() else None
    request = ForceRequest(True, reason)
    operation = {'op': 'resource_replace', 'path': path,
        'observed_byte_sha256': expected if expected is not None else 'absent' if before is None else sha256(before).hexdigest(),
        'target': {'delete': True} if raw is None else {'bytes_base64': base64.b64encode(raw).decode('ascii')},
        'reason': 'Explicit synthetic replacement', 'force': request.data}
    return prepare_resource_plan(operations=[operation], project_id=json.loads((root/'specroad.json').read_bytes())['project_id'],
        actor=ACTOR, request_id=request_id, planned_at='2026-11-23T00:00:00Z', change_plan_id='explicit-force-plan', force=True, reason=reason)
