"""Analyzer snapshot/subject transitions into the shared Work journal codec."""
from pathlib import Path
from hashlib import sha256
from ..analyzers._values import encoded, require
from ..analyzers.identities import AnalysisRequestId
from ..analyzers.requests import AnalyzerRequest
from ..analyzers.files import InputFile
from ..analyzers.subjects import request_from_project
from .manifest import (_partition, _tree, _put, _task_binding,
    partition_work_manifest, complete_work_manifest)

SNAPSHOT = 'request.json'


def _guards(control):
    if control['project'] is not None:
        root = Path(control['project'])
        require(root.resolve(strict=True) == root, 'analyzer_work_project_changed', exit_code=6)
        info = root.stat()
        require([info.st_dev,info.st_ino] == control['project_identity'], 'analyzer_work_project_changed', exit_code=6)
    for item in control['guards']:
        current = InputFile(item['path'], control['cwd'])
        require(current.raw.hex() == item['raw_hex'], 'analyzer_work_input_changed', exit_code=6)
        current.current()


def _capture(control, identity):
    _guards(control)
    request = (AnalyzerRequest(encoded(control['request'])) if control['request'] is not None else
        request_from_project(Path(control['project']), **control['supplied'],
            subject_ids=control['subject_ids'], field_pointers=control['field_pointers'],
            configuration_id=control['configuration_id'], analysis_id=AnalysisRequestId(identity)))
    _guards(control)
    return request


def advance(manifest, *, executor=None):
    """One complete native unit; no output publication or journal mutation."""
    from .analyzer import checked
    from ..analyzers._work_worker import WorkWorker
    control, _, _ = checked(manifest)
    if executor is None and control['format_version'] == 'analyzer-work-request-v2':
        with WorkWorker() as worker:
            return advance(manifest, executor=worker)
    from .analyzer import units, engines, completed_result
    control, request, done = checked(manifest)
    value = manifest.as_dict()
    require(value['state'] in ('running','completed'), 'analyzer_work_not_running', exit_code=6)
    if value['state'] == 'completed': return manifest
    real = control['format_version'] == 'analyzer-work-request-v2'
    def current_engines(request):
        if not real: return engines(request)
        if value['command_id'] == 'analyzer.request':
            from ..analyzers._work_values import static_engines
            return static_engines(request)
        return executor.engines(request)
    if request is None:
        request = _capture(control, value['normalized_arguments']['analysis_id'])
        objects = dict(manifest.objects)
        rows = manifest.entries('inputs')
        rows.append(dict(root_id='analyzer', path=SNAPSHOT, **_put(request.canonical_bytes,objects)))
        value['manifests']['inputs'] = _tree('inputs', sorted(rows,key=lambda r:(r['root_id'],r['path'])), objects)
        command = {k:value[k] for k in ('command_id','command_class','normalized_arguments')}
        binding = _task_binding(command, value['source_bindings'], '', {})
        tasks = [dict(unit, unit_id='UNIT-'+sha256(encoded({'binding':binding,'unit':unit})).hexdigest())
                 for unit in units(request, value['command_id'])]
        value['manifests']['tasks'] = _tree('tasks', tasks, objects)
        complete = [{'unit_id':tasks[0]['unit_id'], 'evidence':_put(encoded({'request_sha256':sha256(request.canonical_bytes).hexdigest(),'engines':current_engines(request)}),objects)}]
        value['checkpoint_generation'] += 1
        return _partition(value,tasks,complete,objects,manifest._registry,value['tool_build'])
    # A fully computed report never needs a worker again. Only new subject
    # computation must re-observe the bound engine in this invocation.
    remaining = manifest.entries('remaining')
    if not real or remaining and remaining[0]['phase'] == 'subjects':
        require(current_engines(request) == done['snapshot']['engines'],
                'analyzer_work_engine_changed', exit_code=5 if real else 6)
    if manifest.entries('remaining'):
        task = manifest.entries('remaining')[0]
        evidence = {'prepared':True}
        if task['phase']=='subjects':
            from ._analyzer_results import prepare_subject
            evidence = (executor.subject(request, task['range']) if real
                        else prepare_subject(request,task))
        return partition_work_manifest(manifest, {task['unit_id']: encoded(evidence)})
    result, code = completed_result(request, value['command_id'], control, done)
    return complete_work_manifest(manifest, result.data, exit_code=code)
