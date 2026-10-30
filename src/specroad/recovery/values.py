"""Owned restore bytes. A valid plan is neither authorization nor a backup."""
from dataclasses import dataclass
from functools import wraps
from hashlib import sha256

from ..model.errors import ModelError
from ..security import SafetyViolation
from ..storage.json_syntax import parse_json_object


class RestoreError(ModelError):
    def __init__(self, reason, *, path=None, exit_code=3, mutation_possible=False,
                 recovery_required=False):
        super().__init__(reason, path=path)
        self.exit_code = exit_code
        self.mutation_possible = mutation_possible
        self.recovery_required = recovery_required

    def diagnostic(self):
        return {**super().diagnostic(), 'exit_code': self.exit_code,
                'mutation_possible': self.mutation_possible,
                'recovery_required': self.recovery_required}


def require(condition, reason, *, path=None, exit_code=3):
    if not condition:
        raise RestoreError(reason, path=path, exit_code=exit_code)


def guarded(function):
    @wraps(function)
    def call(*args, **kwargs):
        from ..bundles.errors import BundleError
        try:
            return function(*args, **kwargs)
        except RestoreError:
            raise
        except SafetyViolation as error:
            raise RestoreError('restore_unsafe_input', exit_code=7) from error
        except (ModelError, BundleError) as error:
            unsafe = error.reason in ('unsafe_path', 'reserved_path', 'unsafe_project_declaration')
            raise RestoreError(error.reason, path=getattr(error, 'path', None),
                exit_code=7 if unsafe else getattr(error, 'exit_code', 3),
                mutation_possible=getattr(error, 'mutation_possible', False)) from error
        except FileNotFoundError as error:
            raise RestoreError('restore_required_source_missing') from error
        except OSError as error:
            raise RestoreError('restore_io', exit_code=5) from error
        except RecursionError as error:
            raise RestoreError('restore_recursive_input_invalid') from error
    return call


def persisted_contract(function):
    """Malformed inert recovery data is an invalid proof, never executable input."""
    @wraps(function)
    def call(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (ModelError, SafetyViolation):
            # Structured contract/conflict/security failures already have
            # their own diagnostic and must not collapse into shape errors.
            raise
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            raise RestoreError('restore_persisted_proof_invalid') from error
    return call


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
