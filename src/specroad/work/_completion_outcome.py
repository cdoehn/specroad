"""Completed command results, separate from checkpoint state transitions."""

from ..cli.requests import CommandRequest
from ..cli.result_schemas import ENVELOPE_ID, validate_result_document
from ..cli.results import FailureKind
from ._data_contract import _require


def check_completed_controls(document):
    """Retain typed-result control invariants when restoring passive JSON."""
    summary = document['summary']
    # The field schema allows command details. These names are nevertheless
    # reserved by CommandResult for partial/external/continuation producers.
    forbidden = {'partial_scope', 'delivery', 'work_id', 'completed_units',
                 'total_units', 'remaining_manifest_sha256', 'checkpoint', 'next_action'}
    _require(not forbidden.intersection(summary))
    _require(document['status'] == 'failed' or 'failure_kind' not in summary)


def _outcome(value, document, exit_code, registry):
    _require(value['command_class'] == 'read_only')
    invocation = registry.bind_request(CommandRequest(value['command_id'], **value['normalized_arguments']))
    validate_result_document(ENVELOPE_ID, document)
    _require(document['command'] == value['command_id']
             and document['summary']['complete'] is True
             and document['result_ref'] is None
             and document['status'] in ('success', 'failed'))
    check_completed_controls(document)
    _require(type(exit_code) is int and exit_code in range(8)
             and exit_code in invocation.command.protocol.handler_exit_codes)
    _require(all(row['code'] in invocation.command.protocol.diagnostic_codes
                 for row in document['diagnostics']))
    if document['status'] == 'success':
        _require(exit_code == 0)
        validate_result_document(invocation.command.protocol.result_schema, document['result'])
    else:
        _require(exit_code != 0 and document['summary'].get('failure_kind')
                 == FailureKind(exit_code).name.lower())
        if document['result'] is not None:
            validate_result_document(invocation.command.protocol.result_schema, document['result'])
