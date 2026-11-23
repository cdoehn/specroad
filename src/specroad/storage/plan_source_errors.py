"""Physical source diagnostics shared by parser and source scanners."""
from ..model.errors import ModelError


class PlanSourceError(ModelError):
    def diagnostic(self):
        identity_error = self.reason in ('duplicate_artifact_id', 'duplicate_plan_display_id',
            'duplicate_plan_relation_id', 'duplicate_plan_claim_id', 'plan_carrier_identity_mismatch',
            'artifact_identity_mismatch')
        return {**super().diagnostic(), 'code': 'SRV201' if identity_error else 'SRV200',
                'severity': 'error', 'partial_result_available': False}


def _error(reason, raw, path, offset, *, pointer=''):
    offset = min(max(offset, 0), len(raw))
    prefix = raw[:offset]
    return PlanSourceError(reason, path=path, position=offset, line=prefix.count(b'\n') + 1,
        column=len(prefix.rsplit(b'\n', 1)[-1].decode('utf-8', errors='replace')) + 1, pointer=pointer)
