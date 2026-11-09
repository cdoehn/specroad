"""Passive success/failure projections, independent of writers and revisions."""
from hashlib import sha256

from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from ..model.record_contracts import SPECIAL_STATES
from ..storage.json_syntax import parse_json_object


def validation_success(context):
    original = context.original
    value = original.data
    report = dict(format_version='proposal-validation-v1',
        validation_scope='proposal_structure_and_applicability', passed=True,
        observed_status=value['proposal_status'],
        eligible_transition='validated' if value['proposal_status'] == 'draft' else None,
        revision=value['revision'], binding=original.binding.data,
        proposal_sha256=original.sha256, context_sha256=context.sha256,
        failure_reason=None, full_semantic_validation=False,
        approval_granted=False, write_authorized=False)
    report['result_sha256'] = canonical_json_sha256(report)
    return report


def validation_failure(raw, context, reason):
    """Bind a failed observation without promoting malformed data to authority."""
    value = {}
    if raw is not None:
        try:
            value = parse_json_object(raw)
        except ModelError:
            pass
    status = value.get('proposal_status')
    if type(status) is not str or status not in SPECIAL_STATES['proposal'][1]:
        status = None
    revision = value.get('revision')
    if type(revision) is not int or revision < 1:
        revision = None
    report = dict(format_version='proposal-validation-v1',
        validation_scope='proposal_structure_and_applicability', passed=False,
        observed_status=status, eligible_transition=None, revision=revision,
        binding=None if context is None else context.original.binding.data,
        proposal_sha256=None if raw is None else sha256(raw).hexdigest(),
        context_sha256=None if context is None else context.sha256,
        failure_reason=reason, full_semantic_validation=False,
        approval_granted=False, write_authorized=False)
    report['result_sha256'] = canonical_json_sha256(report)
    return report
