"""Owned analyzer construction request; distinct from normative Change Plans."""
from dataclasses import dataclass
import os
from ..analyzers._values import encoded, decode, require
from ..analyzers.identities import prepare_analysis_id, AnalysisRequestId
from ..analyzers.requests import AnalyzerRequest
from ..analyzers.file_adapter import default_inputs, request_inputs
from ..analyzers.files import InputFile
from ..cli.contracts import CommandClass, EffectScope
from ._data_contract import _require, _object, WorkManifestError
from .manifest import _create_manifest
from .resume import _runtime_build

CONTROL = 'construction.json'
COMMANDS = ('analyzer.request','analyzer.run')


@dataclass(frozen=True, init=False)
class AnalyzerWorkRequest:
    _raw: bytes

    def __init__(self, registry, command_id, arguments):
        binding = command_binding(registry, command_id, arguments)
        object.__setattr__(self, '_raw', encoded(binding))

    @property
    def binding(self):
        return decode(self._raw)


def command_binding(registry, command_id, arguments):
    _require(command_id in COMMANDS)
    _object(arguments, ('analysis_id', 'construction'))
    AnalysisRequestId(arguments['analysis_id'])
    control = arguments['construction']
    _object(control, ('format_version','project','supplied','subject_ids','field_pointers',
        'configuration_id','request','guards','output','output_root','cwd','project_identity'))
    _require(control['format_version'] == 'analyzer-work-request-v1')
    _require(type(control['guards']) is list)
    for guard in control['guards']:
        _object(guard, ('path','document','raw_hex'))
        _require(type(guard['raw_hex']) is str)
        try:
            original = bytes.fromhex(guard['raw_hex'])
        except ValueError as error:
            raise WorkManifestError('Invalid captured input bytes') from error
        _require(original.hex() == guard['raw_hex'] and decode(original) == guard['document'])
        _require(type(guard['document']) is dict)
        _absolute(guard['path'])
    for key in ('project','output_root'):
        if control[key] is not None: _absolute(control[key])
    _absolute(control['cwd'])
    identity = control['project_identity']
    if control['project'] is None:
        _require(identity is None)
    else:
        _require(type(identity) is list and len(identity)==2
            and all(type(v) is int and v >= 0 for v in identity))
    pointers = control['field_pointers']
    _require(type(pointers) is list and bool(pointers) and all(type(p) is str for p in pointers)
        and len(pointers)==len(set(pointers)))
    from ..changes._patch_pointer import _pointer
    for pointer in pointers: _pointer(pointer, '/field_pointers')
    subjects = control['subject_ids']
    _require(subjects is None or (type(subjects) is list and bool(subjects)
        and all(type(v) is str and v for v in subjects) and len(subjects)==len(set(subjects))))
    _require(control['configuration_id'] is None or type(control['configuration_id']) is str)
    _require(control['output'] is None or type(control['output']) is str)
    if control['request'] is not None:
        request = AnalyzerRequest(encoded(control['request']))
        _require(command_id == 'analyzer.run' and control['supplied'] is None
            and request.data['request_id'] == arguments['analysis_id'])
    else:
        _require(control['project'] is not None and type(control['supplied']) is dict)
        request_inputs(encoded(control['supplied']), [item['descriptor']['analyzer_id']
            for item in control['supplied']['analyzers']])
    command = registry.resolve(command_id)
    _require(command.command_class is CommandClass.GENERATED_OUTPUT
        and command.effect_scope is EffectScope.EXTERNAL_OUTPUT
        and command.protocol.work.continuation_supported)
    return dict(command_id=command_id, command_class='generated_output',
        normalized_arguments=decode(encoded(arguments)))


def _absolute(value):
    from .root import _path
    _path(value)


def prepare_analyzer_work(invocation):
    from .analyzer import units
    options, resolved = invocation.options, invocation.resolved
    cwd = resolved.working_directory
    guards = []
    def read(path):
        source = InputFile(path, cwd)
        document = decode(source.raw)
        guards.append(dict(path=str(source.path), document=document, raw_hex=source.raw.hex()))
        source.current()
        return document
    # Allocate exactly once, before reading any project snapshot/construction input.
    # Explicit complete requests own their data ID and never generate a new one.
    explicit = read(options['--request']) if '--request' in options else None
    identity = (AnalysisRequestId(AnalyzerRequest(encoded(explicit)).data['request_id'])
        if explicit is not None else prepare_analysis_id(options.get('--analysis-id')))
    root = resolved.project_root
    supplied = None
    if explicit is None:
        require(root is not None and bool(options.get('--analyzer')),
            'analyzer_selection_required', exit_code=2)
        raw = (read(options['--inputs']) if '--inputs' in options
            else default_inputs(read(str(root/'specroad.json'))))
        supplied = request_inputs(encoded(raw), options['--analyzer'])
    output = options.get('--output')
    control = dict(format_version='analyzer-work-request-v1', project=None if root is None else str(root),
        supplied=supplied, subject_ids=None if '--subject' not in options else list(options['--subject']),
        field_pointers=list(options.get('--field', ('/statement',))),
        configuration_id=resolved.values.get('configuration'), request=explicit, guards=guards,
        output=output, output_root=options.get('--output-root'), cwd=str(cwd),
        project_identity=None if root is None else [os.stat(root).st_dev,os.stat(root).st_ino])
    from ..changes._patch_pointer import _pointer
    from ..model.errors import ModelError
    from ..analyzers._values import AnalyzerError
    pointers = control['field_pointers']
    require(bool(pointers) and len(pointers)==len(set(pointers)), 'analyzer_invalid_pointer_selection', exit_code=2)
    try:
        for pointer in pointers: _pointer(pointer, '/field_pointers')
    except ModelError as error:
        raise AnalyzerError(error.reason, pointer=error.pointer, exit_code=2) from error
    require(control['subject_ids'] is None or (bool(control['subject_ids'])
        and len(control['subject_ids'])==len(set(control['subject_ids']))), 'analyzer_duplicate_selection', exit_code=2)
    arguments = dict(analysis_id=identity.value, construction=control)
    command = AnalyzerWorkRequest(invocation.registry, invocation.command.command_id, arguments).binding
    return _create_manifest(invocation.registry, command, tool_build=_runtime_build(),
        source_bindings=dict(project_id=None, scope=[], model_root_sha256=None),
        inputs=[dict(root_id='analyzer', path=CONTROL, raw=encoded(control))],
        units=units(None, invocation.command.command_id))
