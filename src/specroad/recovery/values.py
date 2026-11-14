"""Owned restore bytes. A valid plan is neither authorization nor a backup."""
from dataclasses import dataclass
from hashlib import sha256

from ..qualification.errors import RestoreError, require, guarded, persisted_contract
from ..storage.json_syntax import parse_json_object










@dataclass(frozen=True, init=False)
class RestorePlan:
    """Independently reconstructed passive plan, with detached value access.

    Construction checks embedded original bytes and internal consistency only.
    Current qualification and live origin/inventory checks are separate. No execution
    API, durable backup, recovery lock, journal or approval is implied.
    """
    _raw: bytes

    @guarded
    def __init__(self, raw):
        from ._codec import decode
        from ._plan_checks import verify_contents
        from ._owned_checks import checked_bytes
        def check():
            data, objects = decode(raw)
            verify_contents(data, objects)
        if type(raw) is bytes:
            checked_bytes('restore-plan-v1', raw, check)
        else:
            check()
        object.__setattr__(self, '_raw', raw)

    @property
    def source_bytes(self):
        return self._raw

    @property
    def data(self):
        return parse_json_object(self._raw)

    @property
    def sha256(self):
        """Hash of the actual external bytes, distinct from the inner plan hash."""
        return sha256(self._raw).hexdigest()

    @property
    @guarded
    def history_assessments(self):
        """Detached native historical findings, separate from the closed plan.

        Negative results and stale contexts stay visible. These are neither
        authoritative-run selection nor verification/readiness success.
        """
        from ._validation import project_bytes
        from ._codec import decode
        from ._historical_findings import historical_findings
        data, objects = decode(self._raw)
        files = {r['path']: objects[r['sha256']] for r in data['target']['entries']}
        return historical_findings(project_bytes(files)[0])

    def __bool__(self):
        raise TypeError('A restore plan grants no execution or approval authority')
