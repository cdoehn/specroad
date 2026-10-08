"""Transaction gate for normal calls; automatic recovery ends this invocation.

Trusted hosts supply the real command class and authenticate RecoveryAuthority.
This library neither installs project CLI handlers nor executes a normal change.
The returned observation is not a write capability or a reusable project lease.
"""
from dataclasses import dataclass

from ..cli.contracts import CommandClass
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..security import ProjectBoundary, SafetyViolation
from ..storage.json_syntax import parse_json_object
from ..storage.operational_preflight import observe_operational_preflight
from ..storage.preflight_metadata import MetadataPhases
from .authoring import normalize_request_id
from .execution_values import ChangeExecutionError
from .recovery_values import RecoveryError
from ._journal_codec import _text
from ._preflight_decision import prepare_automatic_recovery
from ._automatic_recovery import recover_selected_transaction


@dataclass(frozen=True, init=False)
class TransactionPreflight:
    _raw: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use transaction_preflight with current project inputs')

    @classmethod
    def _create(cls, data):
        obj = object.__new__(cls)
        object.__setattr__(obj, '_raw', canonical_json_bytes(data))
        return obj

    @property
    def data(self):
        return parse_json_object(self._raw)

    @property
    def exit_code(self):
        return self.data['exit_code']

    def __bool__(self):
        raise TypeError('A transaction preflight is not write authorization')


def transaction_preflight(root, *, command_class, dry_run=False, request_id=None,
                          expected_project_id=None, authority=None, actor=None):
    """Observe first; recover at most one safely selected former transaction.

    Read-only/plan/generated/dry-run calls never read journal bodies or activate
    recovery. A write also needs explicit auto_recover=true and host authority.
    Successful automatic recovery returns code 5 and requires a new invocation;
    the original request is neither executed nor consumed. A clear transaction
    gate still requires the caller's ordinary configuration, model and write checks.
    """
    supported = (CommandClass.READ_ONLY, CommandClass.PLAN_OUTPUT,
                 CommandClass.GENERATED_OUTPUT, CommandClass.NORMATIVE_WRITE)
    if type(command_class) is not CommandClass or command_class not in supported or type(dry_run) is not bool:
        raise RecoveryError('normal_project_call_class_required', exit_code=2)
    if expected_project_id is not None and not _text(expected_project_id):
        raise RecoveryError('preflight_project_identity_required', exit_code=2)
    if request_id is not None:
        normalize_request_id(request_id)
    data = {'format_version': 'transaction-preflight-v1', 'command_class': command_class.value,
            'dry_run': dry_run, 'request_id': request_id, 'request_consumed': False,
            'phase': 'transaction_metadata', 'exit_code': 5, 'reason': 'recovery_required',
            'transaction_preflight_passed': False, 'normal_operation_started': False,
            'model_loaded': False, 'write_authorized': False, 'atomic_snapshot': False,
            'recovery_required': True, 'recovery_attempted': False, 'recovery_completed': False,
            'requires_new_invocation': False, 'mutation_possible': False, 'recovery': None}
    metadata = MetadataPhases()

    def result():
        data.update(metadata.summary())
        data['diagnostic_codes'] = ['SRV167'] if data['preflight_detail_required'] else []
        return TransactionPreflight._create(data)

    try:
        boundary = ProjectBoundary(root)
        observed = observe_operational_preflight(boundary, metadata=metadata)
        data['operational'] = observed
        if observe_operational_preflight(boundary, metadata=metadata) != observed:
            raise RecoveryError('preflight_operational_metadata_changed', exit_code=6)
        if observed['consistency_state'] == 'consistent':
            data.update(exit_code=0, reason='transaction_gate_clear',
                        recovery_required=False, transaction_preflight_passed=True)
            return result()
        if command_class is not CommandClass.NORMATIVE_WRITE or dry_run:
            return result()
        decision = prepare_automatic_recovery(boundary, observed, data, metadata,
            expected_project_id=expected_project_id, request_id=request_id, authority=authority, actor=actor)
        if decision is not None:
            recover_selected_transaction(decision, data)
        return result()
    except (ChangeExecutionError, ModelError, SafetyViolation, OSError) as error:
        data.update(exit_code=getattr(error, 'exit_code', 5),
                    reason=getattr(error, 'reason', 'transaction_preflight_unavailable'),
                    mutation_possible=data['mutation_possible'] or getattr(error, 'mutation_possible', False))
        return result()
