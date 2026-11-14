"""Shared structured qualification failures, with stable public diagnostics."""
from functools import wraps
from ..model.errors import ModelError
from ..security import SafetyViolation


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
