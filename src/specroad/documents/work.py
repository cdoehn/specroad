"""Durable whole-composition/block units over an explicitly supplied snapshot.

No public CLI or arbitrary stored handler. Native kernels are still atomic and
memory resident; a Work window resumes between them, not within one large query.
"""
from dataclasses import dataclass

from ..cli.contracts import CommandClass, EffectScope, PreflightProfile
from ..cli.registry import CommandRegistry
from ..cli.requests import CommandRequest
from ..cli.results import CommandResult
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..runtime.controlled import _invocation
from ..runtime.control_points import PhaseBoundary
from ..work._data_contract import WorkManifestError, _object, _parse
from ..work.checkpoints import CheckpointStore
from ..work.manifest import (WorkManifest, create_work_manifest, read_work_manifest,
                             partition_work_manifest, complete_work_manifest)
from ..work.resume import WorkResumeError, _compatible_read, _require, _runtime_build
from . import _work_inputs
from ._work_evidence import DocumentEvidence
from .blocks import ContentBlock
from .includes import compose_document
from .prose import parse_prose
from .references import resolve_artifact_reference
from .tables import resolve_table_block

_REQUEST = CommandRequest('document.project')
_SCHEMA = 'document-work-v1'


def _contract(registry):
    _require(type(registry) is CommandRegistry, 'trusted_document_registry_required')
    command = registry.bind_request(_REQUEST).command
    _require(command.command_class is CommandClass.READ_ONLY
        and command.effect_scope is EffectScope.NONE
        and command.preflight_profile is PreflightProfile.BOOTSTRAP
        and command.protocol is not None and command.protocol.result_schema == _SCHEMA
        and 0 in command.protocol.handler_exit_codes, 'unsupported_document_contract')


def _sources(context):
    return {'project_id': context['project_id'], 'scope': ['explicit_saved_model'],
            'model_root_sha256': context['model_root_sha256']}


def prepare_document_work(registry, model, document_id):
    """Capture full owned input bytes without composition, file I/O or execution."""
    _contract(registry)
    model, context, inputs = _work_inputs.capture(model, document_id)
    return create_work_manifest(registry, _REQUEST, tool_build=_runtime_build(),
        source_bindings=_sources(context), inputs=inputs,
        units=_work_inputs.declarations(context, model.artifacts))


def _checked_plan(current, registry, build):
    _contract(registry)
    _require(type(current) is WorkManifest, 'checked_work_required')
    checked = _compatible_read(read_work_manifest, current.raw, current.objects,
                              registry=registry, expected_tool_build=build)
    context, inputs = _work_inputs.saved(checked)
    value = checked.as_dict()
    _require(value['command_id'] == _REQUEST.command_id
        and value['normalized_arguments'] == {'arguments': {}, 'options': {}}
        and value['source_bindings'] == _sources(context)
        and value['state'] in ('running', 'completed'), 'unsupported_document_plan')
    declarations = _work_inputs.declarations(context,
        [_parse(inputs['project', p]) for p in context['documents']])
    tasks = checked.entries('tasks')
    _require(len(tasks) == len(declarations) and all(
        {k: task[k] for k in ('key', 'phase', 'range')} == declared
        for task, declared in zip(tasks, declarations)), 'document_task_inventory_changed')
    return checked


def _records(current):
    """Read the bound completed prefix; never repeat a confirmed native kernel."""
    tasks, completed = current.entries('tasks'), current.entries('completed')
    _require([i['unit_id'] for i in completed] == [t['unit_id'] for t in tasks[:len(completed)]],
             'document_completion_must_be_prefix')
    context, inputs = _work_inputs.saved(current); value = current.as_dict(); records = []
    evidence = DocumentEvidence(context, inputs)
    for item, task in zip(completed, tasks):
        raw = current.objects[item['evidence']['sha256']]; row = _parse(raw)
        _object(row, ('format_version', 'unit_id', 'input_manifest_sha256',
                      'task_manifest_sha256', 'kind', 'artifact_id', 'selected', 'observation'))
        _require(canonical_json_bytes(row) == raw and row['format_version'] == 'document-work-unit-v1'
            and row['unit_id'] == task['unit_id'] and row['kind'] == task['range']['kind']
            and row['artifact_id'] == task['range']['artifact_id']
            and row['input_manifest_sha256'] == value['input_manifest_sha256']
            and row['task_manifest_sha256'] == value['task_manifest_sha256']
            and type(row['selected']) is bool, 'invalid_document_completion')
        data = row['observation']
        if row['kind'] == 'compose':
            _require(row['selected'] is True, 'invalid_document_composition')
            evidence.composition(data)
        else:
            selected = row['artifact_id'] in records[0]['observation']['records']
            _require(row['selected'] is selected, 'document_block_selection_changed')
            if not selected:
                _require(data is None, 'unselected_document_block_executed')
            else:
                bound = records[0]['observation']['records'][row['artifact_id']]
                block = ContentBlock(inputs['project', bound['path']], path=bound['path'])
                _require(type(data) is dict and data.get('block') == block.binding,
                         'document_block_binding_changed')
                if block.block_kind in ('query', 'table'):
                    evidence.table(block, data)
                elif block.block_kind in ('prose', 'admonition'):
                    evidence.prose(block, data)
                elif block.block_kind == 'artifact_ref':
                    evidence.reference(block, data)
                else:
                    _require(data == _passive(block), 'invalid_document_passive_block')
        if data is not None:
            _require(all(data.get(flag) is False for flag in
                ('rendering_performed', 'write_authorized', 'approval_granted')),
                'invalid_document_authority')
        records.append(row)
    return records


def _passive(block):
    return {'kind': 'document-passive-block-v1', 'block': block.binding,
        'record': block.data, 'rendering_performed': False,
        'write_authorized': False, 'approval_granted': False}


def _evaluate(current, task, model, rows):
    job = task['range']; identifier = job['artifact_id']; selected = True
    if job['kind'] == 'compose':
        observation = compose_document(model, identifier).data
    else:
        bound = rows[0]['observation']['records'].get(identifier)
        selected = bound is not None; observation = None
        if selected:
            block = ContentBlock(model.source_files[bound['path']], path=bound['path'])
            if block.block_kind in ('query', 'table'):
                observation = resolve_table_block(model, identifier).data
            elif block.block_kind == 'artifact_ref':
                observation = resolve_artifact_reference(model, identifier).data
            elif block.block_kind in ('prose', 'admonition'):
                observation = parse_prose(block).data
            else:
                observation = _passive(block)
    value = current.as_dict()
    return {'format_version': 'document-work-unit-v1', 'unit_id': task['unit_id'],
        'input_manifest_sha256': value['input_manifest_sha256'],
        'task_manifest_sha256': value['task_manifest_sha256'], 'kind': job['kind'],
        'artifact_id': identifier, 'selected': selected, 'observation': observation}


def _outcome(current):
    rows = _records(current)
    _require(not current.entries('remaining'), 'unfinished_document_cannot_complete')
    value = current.as_dict()
    return CommandResult(_REQUEST.command_id, result={'format_version': _SCHEMA,
        'input_manifest_sha256': value['input_manifest_sha256'],
        'task_manifest_sha256': value['task_manifest_sha256'],
        'source_scope': 'explicit_saved_model', 'project_files_verified': False,
        'composition': rows[0]['observation'],
        'blocks': [{'artifact_id': r['artifact_id'], 'observation': r['observation']}
                   for r in rows[1:] if r['selected']]})


def _checked_final(current, registry):
    if current.as_dict()['state'] == 'completed':
        from ..work._completion import read_completion
        saved = read_completion(current.as_dict(), current.objects, registry)
        _require(saved['exit_code'] == 0 and canonical_json_bytes(saved['outcome'])
                 == canonical_json_bytes(_outcome(current).as_dict()), 'document_final_result_changed')


def _checked_store(store, registry, build):
    _require(type(store) is CheckpointStore, 'trusted_work_store_required')
    initial = _compatible_read(_checked_plan, store._initial, registry, build)
    _require(initial.as_dict()['checkpoint_generation'] == 0 and not initial.entries('completed'),
             'initial_work_required')
    current = _compatible_read(store.read)
    _require(current is not None, 'published_work_required')
    current = _compatible_read(_checked_plan, current, registry, build)
    _compatible_read(_records, current); _compatible_read(_checked_final, current, registry)
    return current


@dataclass(frozen=True)
class DocumentWorkStep:
    manifest: WorkManifest
    executed_unit_ids: tuple
    reused_unit_ids: tuple
    outcome_bytes: bytes | None = None
    command_exit_code: int | None = None


def advance_document_work(store, call, *, registry, max_units=1):
    """Persist a nonempty prefix; a soft window always attempts one real unit."""
    _invocation(call)
    _require(type(max_units) is int and max_units > 0, 'invalid_document_window')
    build = _runtime_build(); _checked_store(store, registry, build)
    executed, reused = [], []; native_error = None

    def advance(previous):
        nonlocal native_error
        current = _checked_plan(previous, registry, _runtime_build())
        _checked_final(current, registry)
        rows = _records(current); reused.extend(r['unit_id'] for r in rows)
        if not current.entries('remaining'):
            return previous
        model = _work_inputs.restore(current, store._location); additions = {}
        for task in current.entries('remaining')[:max_units]:
            call.control(PhaseBoundary('work_unit', 'start'))
            try:
                row = _evaluate(current, task, model, rows)
            except ModelError as error:
                native_error = error
                raise
            rows.append(row); additions[task['unit_id']] = canonical_json_bytes(row)
            executed.append(task['unit_id'])
            if call.control(PhaseBoundary('work_unit', 'end'))['soft_budget_exceeded']:
                break
        _require(_runtime_build() == build, 'runtime_build_changed')
        candidate = partition_work_manifest(current, additions); _records(candidate)
        return candidate

    try:
        confirmed = store._update(advance)
    except (WorkManifestError, ModelError) as error:
        if error is native_error:
            raise
        raise WorkResumeError('incompatible_work_contract') from error
    _require(_runtime_build() == build, 'runtime_build_changed')
    return DocumentWorkStep(confirmed, tuple(executed), tuple(reused))


def finalize_document_work(store, *, registry):
    """Close only after all declared units; retain the complete data projection."""
    build = _runtime_build(); current = _checked_store(store, registry, build)
    _outcome(current)  # Refuse unfinished work before taking a writing lease.
    saved = {}

    def finish(previous):
        current = _checked_plan(previous, registry, _runtime_build())
        _checked_final(current, registry); outcome = _outcome(current); saved['outcome'] = outcome
        _require(_runtime_build() == build, 'runtime_build_changed')
        return previous if current.as_dict()['state'] == 'completed' else complete_work_manifest(
            current, outcome.as_dict(), exit_code=0)

    confirmed = _compatible_read(store._update, finish)
    _require(_runtime_build() == build, 'runtime_build_changed')
    return DocumentWorkStep(confirmed, (), tuple(r['unit_id'] for r in _records(confirmed)),
                            canonical_json_bytes(saved['outcome'].as_dict()), 0)
