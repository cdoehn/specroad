"""Resume a closed built-in read-only handler plan from durable work bytes.

This initial embedding API executes real Core handlers. It does not install a
CLI command, approve Code 8 or declare the surrounding work globally complete.
Only a recorded running distribution and an independently trusted initial work
binding may enter this path. No callable or executable code comes from storage.
"""

from dataclasses import dataclass

from .. import runtime
from ..cli.application import execute_request
from ..cli.commands import builtin_registry
from ..cli.contracts import CommandClass, EffectScope, PreflightProfile
from ..cli.invocation_context import InvocationContextBuilder
from ..cli.requests import CommandRequest
from ..cli.result_schemas import ENVELOPE_ID, validate_result_document
from ..model.canonical import canonical_json_bytes
from ..runtime.identity import version_info
from ._data_contract import _parse, _object
from .checkpoints import CheckpointStore
from .manifest import (WorkManifest, create_work_manifest, read_work_manifest,
                       partition_work_manifest)


_COMMANDS = frozenset(('help', 'version', 'command.describe', 'capabilities',
                       'schema.list', 'schema.show'))
_SOURCES = {'project_id': None, 'scope': [], 'model_root_sha256': None}
_ADAPTER = 'read-only-handler-v1'


class WorkResumeError(ValueError):
    """A concrete refusal to execute or confirm the saved command."""

    def __init__(self, reason, *, exit_code=6):
        super().__init__(reason)
        self.reason, self.exit_code = reason, exit_code

    def as_dict(self):
        return {'reason': self.reason, 'exit_code': self.exit_code}


def _require(condition, reason):
    if not condition:
        raise WorkResumeError(reason)


def _runtime_build():
    runtime.check_runtime()
    value = version_info()
    if value['build_identity_status'] != 'recorded':
        raise WorkResumeError('recorded_runtime_build_required', exit_code=5)
    return {'version': value['program_version'], 'build_sha256': value['build_sha256'],
            'hash_algorithm': value['build_hash_algorithm']}


def _declaration(command_id):
    return {'key': 'builtin-handler', 'phase': 'execute',
            'range': {'adapter': _ADAPTER, 'command_id': command_id}}


def _invocation(registry, request):
    _require(type(request) is CommandRequest and request.command_id in _COMMANDS
             and not request.options, 'unsupported_resume_request')
    invocation = registry.bind_request(request)
    command = invocation.command
    _require(command.command_class is CommandClass.READ_ONLY
             and command.effect_scope is EffectScope.NONE
             and command.preflight_profile is PreflightProfile.BOOTSTRAP,
             'unsupported_resume_contract')
    return invocation


def prepare_read_only_work(request):
    """Plan exactly one complete supported Core handler without executing it.

    The caller separately publishes generation zero and retains its trusted
    binding. Unsealed source checkouts cannot invent a compatible build identity.
    """
    registry, build = builtin_registry(), _runtime_build()
    _invocation(registry, request)
    return create_work_manifest(registry, request, tool_build=build,
        source_bindings=_SOURCES, inputs=[], units=[_declaration(request.command_id)])


def _checked_plan(manifest, registry, build):
    _require(type(manifest) is WorkManifest, 'checked_work_required')
    _require(manifest.as_dict()['tool_build'] == build, 'incompatible_runtime_build')
    current = read_work_manifest(manifest.raw, manifest.objects, registry=registry,
                                 expected_tool_build=build)
    value = current.as_dict()
    request = CommandRequest(value['command_id'], **value['normalized_arguments'])
    invocation = _invocation(registry, request)
    _require(value['source_bindings'] == _SOURCES and current.entries('inputs') == [],
             'unsupported_resume_inputs')
    tasks = current.entries('tasks')
    _require(len(tasks) == 1 and {k: v for k, v in tasks[0].items() if k != 'unit_id'}
             == _declaration(request.command_id), 'unsupported_resume_plan')
    return current, request, invocation, tasks[0]['unit_id']


def _checked_outcome(document, invocation, exit_code):
    validate_result_document(ENVELOPE_ID, document)
    _require(document['command'] == invocation.command.command_id
             and document['summary']['complete'] is True
             and document['result_ref'] is None
             and document['status'] in ('success', 'failed'), 'incomplete_resume_outcome')
    _require(type(exit_code) is int and exit_code in range(8), 'invalid_resume_exit_code')
    if document['status'] == 'success':
        _require(exit_code == 0, 'invalid_resume_exit_code')
        validate_result_document(invocation.command.protocol.result_schema, document['result'])
    else:
        from ..cli.results import FailureKind
        _require(exit_code != 0 and document['summary'].get('failure_kind')
                 == FailureKind(exit_code).name.lower(), 'invalid_resume_exit_code')
    return document


def _saved_outcome(current, request, invocation, unit_id):
    completed = current.entries('completed')
    _require(len(completed) == 1 and completed[0]['unit_id'] == unit_id,
             'invalid_resume_completion')
    raw = current.objects[completed[0]['evidence']['sha256']]
    record = _parse(raw)
    _object(record, ('format_version', 'unit_id', 'request', 'tool_build', 'exit_code', 'outcome'))
    _require(record['format_version'] == 'read-only-handler-evidence-v1'
             and record['unit_id'] == unit_id and record['request'] == request.as_dict()
             and record['tool_build'] == current.as_dict()['tool_build']
             and canonical_json_bytes(record) == raw, 'invalid_resume_completion')
    return _checked_outcome(record['outcome'], invocation, record['exit_code']), record['exit_code']


@dataclass(frozen=True)
class ReadOnlyResumeStep:
    """Saved handler output; the WorkManifest still requires later finalization."""

    manifest: WorkManifest
    outcome_bytes: bytes
    command_exit_code: int
    executed: bool

    def as_dict(self):
        value = self.manifest.as_dict()
        return {'format_version': 'read-only-resume-step-v1', 'work_id': value['work_id'],
                'checkpoint_generation': value['checkpoint_generation'],
                'checkpoint_sha256': value['checkpoint_sha256'], 'work_state': value['state'],
                'next_action': value['next_action'], 'executed': self.executed,
                'command_exit_code': self.command_exit_code, 'command_outcome': _parse(self.outcome_bytes)}


def resume_read_only_work(store, *, cwd=None):
    """Freshly check, execute once and durably save the supported handler unit.

    Already saved output is checked and reused. No registry, actor, request,
    argument, build or plan override is accepted. The caller supplies the
    independently trusted CheckpointStore binding and current protected roots.
    """
    _require(type(store) is CheckpointStore, 'trusted_work_store_required')
    registry, build = builtin_registry(), _runtime_build()
    # Reject missing/incompatible work before a writer lease could allocate data.
    initial, _, _, _ = _checked_plan(store._initial, registry, build)
    _require(initial.as_dict()['checkpoint_generation'] == 0, 'initial_work_required')
    current = store.read()
    _require(current is not None, 'published_work_required')
    _checked_plan(current, registry, build)
    saved = {}

    def advance(previous):
        # This second read is under the lease retained through publication.
        current, request, invocation, unit_id = _checked_plan(previous, registry, _runtime_build())
        InvocationContextBuilder().prepare(invocation, cwd=cwd)
        if current.entries('completed'):
            outcome, exit_code = _saved_outcome(current, request, invocation, unit_id)
            saved.update(outcome=outcome, exit_code=exit_code, executed=False)
            return previous
        response = execute_request(request, registry=registry, cwd=cwd)
        outcome, exit_code = response.result.as_dict(), response.result.exit_code
        if not response.result.complete:
            raise WorkResumeError('command_did_not_complete', exit_code=exit_code)
        _checked_outcome(outcome, invocation, exit_code)
        raw = canonical_json_bytes({'format_version': 'read-only-handler-evidence-v1',
            'unit_id': unit_id, 'request': request.as_dict(), 'tool_build': build,
            'exit_code': exit_code, 'outcome': outcome})
        following = partition_work_manifest(current, {unit_id: raw})
        saved.update(outcome=outcome, exit_code=exit_code, executed=True)
        return following

    confirmed = store._update(advance)
    return ReadOnlyResumeStep(confirmed, canonical_json_bytes(saved['outcome']),
                             saved['exit_code'], saved['executed'])
