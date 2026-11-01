"""Durable outbound stages, bound to one source and one producing attempt.

An interrupted intent without a captured Result is deliberately not retried.
Captured Result bytes are identified by their external hash. Later invocations
recheck the original source and prepare a fresh opaque public export plan.
"""
from contextlib import nullcontext
from pathlib import Path

from ..cli.requests import CommandRequest
from ..cli.results import CommandResult
from ..cli.result_schemas import validate_result_document
from ..model.canonical import canonical_json_bytes
from ..storage.json_syntax import parse_json_object
from ..transport._files import require
from ..transport.outbound import OutboundExport
from ._request_binding import _command
from .manifest import (_create_manifest, _bytes, _entries, partition_work_manifest,
                       complete_work_manifest)
from .restore_execution import _build
from ._public_errors import work_errors


_PHASES = ('export_intent', 'capture_reference', 'assemble_handoff', 'publish_handoff')
_SOURCES = {'project_id': None, 'scope': ['project'], 'model_root_sha256': None}


def _units():
    return [{'key': name, 'phase': name, 'range': {'adapter': 'source-safe-outbound-v1'}}
            for name in _PHASES]


def _export(options, *, recover=False):
    return OutboundExport(options['--project'], output_root=options['--output-root'],
        output=options['--output'], runtime_reference=options['--runtime-reference'],
        runtime_reference_sha256=options['--runtime-reference-sha256'],
        specroad_pyz=options['--specroad-pyz'], specroad_pyz_sha256=options['--specroad-pyz-sha256'],
        allow_existing=recover)


def protected_paths(initial):
    options, bound, _ = checked(initial)
    return tuple(sorted({options[key] for key in ('--project', '--output-root',
        '--specroad-pyz', '--runtime-reference')} | {bound['repository_root']}))


def _checked(value, objects, inputs, tasks, completed):
    require(value['command_id'] == 'bundle.create' and value['command_class'] == 'transport_operational'
            and value['source_bindings'] == _SOURCES, 'outbound_work_binding_invalid')
    require(len(inputs) == 1 and inputs[0]['root_id'] == 'outbound'
            and inputs[0]['path'] == 'source.json', 'outbound_work_source_invalid')
    bound = parse_json_object(_bytes({k: inputs[0][k] for k in ('sha256','size')}, objects))
    require(set(bound) == {'source_binding', 'repository_root', 'project_path', 'plan_sha256',
                          'coverage_sha256', 'core_sha256', 'runtime_reference_sha256'},
            'outbound_work_source_invalid')
    require([{k: unit[k] for k in ('key','phase','range')} for unit in tasks] == _units()
            and [row['unit_id'] for row in completed] == [t['unit_id'] for t in tasks[:len(completed)]],
            'outbound_work_units_invalid')
    evidence = [parse_json_object(_bytes(row['evidence'], objects)) for row in completed]
    fields = ({'source'}, {'reference'}, {'sha256','size'}, {'result'})
    for index, row in enumerate(evidence):
        require(set(row) == {'phase','work_id'} | fields[index]
                and row['phase'] == _PHASES[index] and row['work_id'] == value['work_id'],
                'outbound_work_progress_invalid')
    if evidence:
        require(evidence[0]['source'] == bound, 'outbound_work_intent_changed')
    if len(evidence) >= 2:
        reference = evidence[1]['reference']
        require(set(reference) == {'path','sha256','source_binding','effects'}
                and reference['source_binding'] == bound['source_binding'], 'outbound_work_reference_changed')
    if len(evidence) == 4:
        result = evidence[3]['result']
        validate_result_document('bundle-create-v1', result)
        require(result['file']['sha256'] == evidence[2]['sha256']
                and result['file']['size'] == evidence[2]['size'], 'outbound_work_result_changed')
    return value['normalized_arguments']['options'], bound, evidence


def checked(current):
    return _checked(current.as_dict(), current.objects, current.entries('inputs'),
                    current.entries('tasks'), current.entries('completed'))


def final_outcome(value, objects, document, exit_code):
    _, _, evidence = _checked(value, objects,
        *(_entries(k, value['manifests'][k], objects) for k in ('inputs','tasks','completed')))
    require(len(evidence) == 4 and exit_code == 0 and evidence[-1]['result'] == document,
            'outbound_work_not_complete')


@work_errors
def start(invocation):
    from .root import WorkDirectory
    from .checkpoints import CheckpointStore
    from ..cli.work_handler import continuation
    build = _build()
    options = dict(invocation.options)
    export = _export(options)
    export.prepare()
    request = CommandRequest('bundle.create', options, dict(invocation.arguments))
    initial = _create_manifest(invocation.registry, _command(invocation.registry, request, transport=True),
        tool_build=build, source_bindings=_SOURCES,
        inputs=[{'root_id':'outbound', 'path':'source.json', 'raw':canonical_json_bytes(export.expected_source())}],
        units=_units())
    location = WorkDirectory(initial, protected_roots=(), protected_paths=protected_paths(initial),
                             directory=options.get('--work-dir'))
    store = CheckpointStore(location, initial)
    with location.for_checkpoint(require_empty=True) as held:
        store._publish_held(held, initial, None)
    return continuation('bundle.create', store, initial)


@work_errors
def resume(store):
    """Advance a bounded native stage. Never repeat an ambiguous PH export."""
    with store._location.inspect_checkpoint() as held:
        pointer = store._pointer(held)
        require(pointer is not None, 'outbound_work_missing', 5)
        current = store._read_chain(held, pointer[0])
        _, _, evidence = checked(current)
        if current.as_dict()['state'] == 'completed':
            return current, evidence[-1]['result']
    with store._location.for_checkpoint() as held:
        pointer = store._pointer(held)
        require(pointer is not None, 'outbound_work_missing', 5)
        current = store._read_chain(held, pointer[0])
        options, bound, evidence = checked(current)
        require(current.as_dict()['state'] == 'running', 'outbound_work_cancelled', 6)
        require(len(evidence) != 1, 'outbound_export_interrupted_requires_inspection', 6)
        if len(evidence) == 4:
            # A terminal-checkpoint failure does not repeat a completed output.
            document = evidence[-1]['result']
            current = store._publish_held(held,
                complete_work_manifest(current, document, exit_code=0), pointer)
            return current, document
        export = _export(options, recover=len(evidence) >= 3)
        export.prepare(expected=bound)

        def save(**data):
            nonlocal current, pointer, evidence
            index = len(evidence)
            value = current.as_dict()
            record = {'phase': _PHASES[index], 'work_id': value['work_id'], **data}
            require(store._pointer(held) == pointer, 'outbound_work_changed', 6)
            candidate = partition_work_manifest(current, {
                current.entries('tasks')[index]['unit_id']: canonical_json_bytes(record)})
            current = store._publish_held(held, candidate, pointer)
            pointer = store._pointer(held)
            evidence.append(record)

        if not evidence:
            # The durable intent precedes the only producing PH call. Failed
            # calls and hard crashes retain this marker and their actual files.
            save(source=bound)
            reference = export.capture()
            save(reference=reference)
            return current, None
        container, verify = export.assemble(evidence[1]['reference'])
        if len(evidence) == 2:
            save(sha256=container.sha256, size=len(container.source_bytes))
        require(evidence[2]['sha256'] == container.sha256
                and evidence[2]['size'] == len(container.source_bytes), 'outbound_work_handoff_changed', 6)
        document = export.publish(container, verify, recover=True)
        save(result=document)
        current = store._publish_held(held,
            complete_work_manifest(current, document, exit_code=0), pointer)
        return current, document


@work_errors
def cancel(store, reason):
    from .control import _cancel
    def check(current):
        _, _, evidence = checked(current)
        require(not evidence, 'outbound_started_work_requires_inspection', 6)
    return _cancel(store, reason, _build(), check, lambda current: nullcontext())
