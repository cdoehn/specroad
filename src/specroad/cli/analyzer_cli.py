"""Real analyzer handlers: passive files, explicit snapshots and honest coverage."""
from hashlib import sha256

from ..analyzers._values import AnalyzerError, decode, encoded, require
from ..analyzers.file_adapter import default_inputs, request_inputs, descriptors, unavailable_package
from ..analyzers.files import InputFile, publish
from ..analyzers.registry import classify_descriptor
from ..analyzers.requests import AnalyzerRequest
from ..analyzers.subjects import request_from_project
from ..analyzers.evaluation import evaluate_reports
from ..analyzers.schemas import schema
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..storage.json_syntax import parse_json_object
from .option_values import policy_exit_code
from .results import CommandResult, FailureKind, OperationFailure
from .result_schemas import validate_result_document


def _inputs(invocation):
    options = invocation.options
    cwd = invocation.resolved.working_directory
    files = []
    def read(path):
        value = InputFile(path, cwd)
        files.append(value)
        return value.raw
    def current():
        for value in files:
            value.current()
    return options, read, files, current


def _request(invocation, read):
    options = invocation.options
    if '--request' in options:
        return AnalyzerRequest(read(options['--request']))
    selected = options.get('--analyzer')
    require(selected, 'analyzer_selection_required', exit_code=2)
    root = invocation.resolved.project_root
    require(root is not None, 'analyzer_project_required', exit_code=2)
    if '--inputs' in options:
        raw = read(options['--inputs'])
    else:
        # Observe configuration through the same bound input reader; do not use
        # the saved request as evidence for current settings.
        config = parse_json_object(read(str(root/'specroad.json')))
        raw = encoded(default_inputs(config))
    supplied = request_inputs(raw, selected)
    return request_from_project(root, **supplied, subject_ids=options.get('--subject'),
        field_pointers=options.get('--field', ('/statement',)), analysis_id=options.get('--analysis-id'),
        configuration_id=invocation.resolved.values.get('configuration'))


def _inspection(invocation, read, files):
    options = invocation.options
    paths = (invocation.arguments['files'] if invocation.command.command_id == 'analyzer.evaluate'
             else (invocation.arguments['file'],))
    raws, sources, unreadable = [], [], []
    for path in paths:
        try:
            raw = read(path)
        except (ModelError, SafetyViolation, OSError) as error:
            failure = 7 if isinstance(error, SafetyViolation) else 5 if isinstance(error, OSError) else getattr(error, 'exit_code', 3)
            unreadable.append((len(raws), failure, getattr(error, 'reason', 'analyzer_file_unavailable')))
            raw = b''
        raws.append(raw)
        try:
            document = decode(raw)
        except AnalyzerError:
            document = None
        sources.append(dict(path=path, size=len(raw), sha256=sha256(raw).hexdigest(), document=document))
    request = AnalyzerRequest(read(options['--request'])) if '--request' in options else None
    supplied = decode(read(options['--inputs'])) if '--inputs' in options else None
    evaluation = evaluate_reports(raws, request=request, project=invocation.resolved.project_root,
        current_inputs=supplied, configuration_id=invocation.resolved.values.get('configuration')).data
    rows = evaluation['reports']
    for index, failure, reason in unreadable:
        for row in rows:
            if row['input_index'] == index:
                row.update(currentness='unavailable', failure_code=failure, reason=reason, source_sha256=None)
        sources[index].update(size=None, sha256=None)
    evaluation['all_reports_current'] = all(row['currentness'] == 'current' for row in rows)
    complete = all(row['report'] is not None and row['request_binding_verified']
                   and row['report']['run_status'] == 'complete' for row in rows)
    findings = [finding['severity'] for row in rows if row['report'] is not None
                for finding in row['report']['findings']]
    failed = bool(policy_exit_code(findings, invocation.resolved))
    current = evaluation['all_reports_current']
    payload = dict(format_version='1.0.0', sources=sources, evaluation=evaluation,
        execution_complete=complete, findings_failed=failed, current_check_passed=current,
        gate_passed=complete and current and not failed, approval_granted=False)
    # Display/import are integrity operations; they may show a valid unavailable
    # report. Evaluate is an explicit current check, never an implicit success.
    codes = [row['failure_code'] for row in rows if row['failure_code'] is not None]
    code = next((c for c in (7, 6, 5, 3, 2, 4) if c in codes), 0)
    if invocation.command.command_id == 'analyzer.evaluate' and not code:
        code = (5 if any(row['currentness'] == 'unavailable' for row in rows) or not complete
                else 6 if not current else 1 if failed else 0)
    return payload, code, raws[0]


def analyzer_command(invocation):
    try:
        options, read, files, current = _inputs(invocation)
        command = invocation.command.command_id
        require('--output-root' not in options or '--output' in options,
            'analyzer_output_option_required', exit_code=2)
        code, output = 0, None
        if command in ('analyzer.list', 'analyzer.describe'):
            rows = descriptors(read(options['--inputs']) if '--inputs' in options else None)
            if command == 'analyzer.describe':
                rows = tuple(d for d in rows if d.data['analyzer_id'] == invocation.arguments['id'])
                require(bool(rows), 'analyzer_unknown_descriptor', exit_code=2)
            payload = dict(format_version='1.0.0', analyzers=[dict(descriptor=d.data,
                availability=classify_descriptor(d), schema_scope='structural_shapes_native_binding_validation_required',
                schemas={name:schema('analyzer-'+name+'-v1') for name in ('descriptor','inputs','request','report','package')})
                for d in rows])
        elif command in ('analyzer.request', 'analyzer.run'):
            request = _request(invocation, read)
            value = request if command == 'analyzer.request' else unavailable_package(request)
            payload, output = value.data, value.canonical_bytes
            if command == 'analyzer.run':
                code = 5
        else:
            payload, code, original = _inspection(invocation, read, files)
            if command == 'analyzer.import' and not code:
                require(all(r['request_binding_verified'] for r in payload['evaluation']['reports']),
                    'analyzer_import_request_required')
                output = original
        current()
        validate_result_document(invocation.command.protocol.result_schema, payload)
        details = ({'execution_complete':False, 'all_languages_confirmed':False, 'gate_passed':False}
                   if command == 'analyzer.run' else {})
        if '--output' in options and output is not None:
            details['publication'] = publish(output, options['--output'], root=invocation.resolved.project_root,
                output_root=options.get('--output-root'), cwd=invocation.resolved.working_directory, check_inputs=current)
        current()
        if code:
            return CommandResult.failed(command, FailureKind(code), complete=True, result=payload, details=details)
        return CommandResult(command, result=payload, details=details)
    except (ModelError, SafetyViolation, OSError) as error:
        code = 7 if isinstance(error, SafetyViolation) else 5 if isinstance(error, OSError) else getattr(error, 'exit_code', 3)
        raise OperationFailure(FailureKind(code), getattr(error, 'reason', 'analyzer_file_unavailable')) from error
