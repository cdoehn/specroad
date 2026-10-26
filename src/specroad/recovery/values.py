"""Owned restore bytes. A valid plan is neither authorization nor a backup."""
from dataclasses import dataclass
from functools import wraps
from hashlib import sha256

from ..model.errors import ModelError
from ..security import SafetyViolation
from ..storage.json_syntax import parse_json_object


class RestoreError(ModelError):
    def __init__(self, reason, *, path=None, exit_code=3):
        super().__init__(reason, path=path)
        self.exit_code = exit_code


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
                exit_code=7 if unsafe else getattr(error, 'exit_code', 3)) from error
        except FileNotFoundError as error:
            raise RestoreError('restore_required_source_missing') from error
        except OSError as error:
            raise RestoreError('restore_io', exit_code=5) from error
        except RecursionError as error:
            raise RestoreError('restore_recursive_input_invalid') from error
    return call


@dataclass(frozen=True, init=False)
class RestorePlan:
    """Independently reconstructed passive plan, with detached value access.

    Construction checks embedded bytes and full supported project gates. Live
    origin/inventory freshness is a separate read-only operation. No execution
    API, durable backup, recovery lock, journal or approval is implied.
    """
    _raw: bytes

    @guarded
    def __init__(self, raw):
        from ._codec import decode
        from ._plan_checks import verify_contents
        data, objects = decode(raw)
        verify_contents(data, objects)
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

    def __bool__(self):
        raise TypeError('A restore plan grants no execution or approval authority')
