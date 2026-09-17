"""Thin projections of typed results into versioned machine contracts.

No execution, policy decisions, truncation, styling or global stream writes.
"""

import json
from urllib.parse import quote

from .._metadata import __version__
from .results import FORMAT_VERSION, ResultContractError, ResultStatus, thaw


def diagnostic_document(diagnostic):
    return {name: thaw(getattr(diagnostic, name)) for name in diagnostic.__dataclass_fields__}


def envelope_document(outcome):
    outcome.verify_delivery()
    summary = thaw(outcome.details)
    summary["complete"] = outcome.complete
    if outcome.failure is not None:
        summary["failure_kind"] = outcome.failure.name.lower()
    if outcome.partial_scope is not None:
        summary["partial_scope"] = outcome.partial_scope
    if outcome.continuation is not None:
        summary.update(outcome.continuation.claim.summary())
    if outcome.result_ref is not None:
        summary["delivery"] = "external"
    return {"format_version": FORMAT_VERSION, "command": outcome.command,
            "status": outcome.status.value, "project": thaw(outcome.project),
            "result": thaw(outcome.result),
            "result_ref": None if outcome.result_ref is None else outcome.result_ref.as_dict(),
            "diagnostics": [item.as_dict() for item in outcome.diagnostics],
            "summary": summary}


def sarif_document(outcome):
    """A closed diagnostic result in SARIF 2.1.0; other states use the envelope.

    Contract: OASIS SARIF 2.1.0, sections 3.13, 3.14, 3.19 and 3.27.
    No imports, analyzer execution, or external schema fetching occur here.
    """
    outcome.verify_delivery()
    if not outcome.complete or outcome.status is ResultStatus.CONTINUATION_REQUIRED:
        return envelope_document(outcome)
    results = []
    for item in outcome.diagnostics:
        record = {"ruleId": item.rule_id or item.code,
                  "level": {"info": "note", "warning": "warning", "error": "error"}[item.severity],
                  "message": {"text": item.message},
                  "properties": {"specroad": diagnostic_document(item)}}
        if item.path:
            record["locations"] = [{"physicalLocation": {"artifactLocation": {
                "uri": quote(item.path.replace("\\", "/"), safe="/")}}}]
        results.append(record)
    return {"version": "2.1.0",
            "$schema": "https://docs.oasis-open.org/sarif/sarif/v2.1.0/cos02/schemas/sarif-schema-2.1.0.json",
            "runs": [{"tool": {"driver": {"name": "SpecRoad", "version": __version__}},
                      "invocations": [{"executionSuccessful": outcome.exit_code in (0, 1),
                                       "exitCode": outcome.exit_code}],
                      "results": results,
                      "properties": {"specroad": envelope_document(outcome)}}]}


def serialize_result(outcome, output_format="json"):
    if output_format == "json":
        document = envelope_document(outcome)
    elif output_format == "sarif":
        document = sarif_document(outcome)
    else:
        raise ResultContractError("Unknown machine format")
    from .result_schemas import ENVELOPE_ID, validate_result_document
    schema_id = "sarif-specroad-v1" if "runs" in document and output_format == "sarif" else ENVELOPE_ID
    validate_result_document(schema_id, document)
    return json.dumps(document, ensure_ascii=True, sort_keys=True, allow_nan=False)
