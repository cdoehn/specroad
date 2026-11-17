"""Small real Proposal Work stores and explicitly synthetic runtime identity."""
import pytest

from specroad import _build
from specroad.cli.application import execute, execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.invocation_context import InvocationContextBuilder
from specroad.work.checkpoints import CheckpointStore
from specroad.work.proposal import prepare_proposal_work, resume_proposal_work, proposal_work_result
from specroad.work.root import WorkDirectory


@pytest.fixture
def recorded(monkeypatch):
    monkeypatch.setattr(_build, 'BUILD_METADATA', {'format_version': 1,
        'hash_algorithm': 'specroad-dev-payload-v1', 'build_sha256': '4'*64})


def store_for(path, root, original):
    initial, protected = prepare_proposal_work(builtin_registry(), root, original.data['id'])
    location = WorkDirectory(initial, protected_roots=protected, directory=path)
    store = CheckpointStore(location, initial)
    store.publish(initial)
    return store


def finish(store, *, window=100000, services=None):
    for _ in range(len(store.read().entries('remaining'))+2):
        current = resume_proposal_work(store, max_units=window, services=services)
        if current.as_dict()['state'] == 'completed':
            return proposal_work_result(store, services=services)
    raise AssertionError('Finite Proposal Work did not reach a complete result')


def invoke(command, *, options=None, arguments=None, services=None, authority=None, form='mapping'):
    options, arguments = options or {}, arguments or {}
    builder = InvocationContextBuilder(restore_services=services, publication_authority=authority)
    if form == 'mapping':
        return execute_request({'command_id': command, 'options': options, 'arguments': arguments},
                               context_builder=builder).result
    args = command.split('.') + list(arguments.values())
    args += [v for k, value in options.items() for v in ([k] if value is True else [k, str(value)])]
    return execute(args, context_builder=builder).result


def work(operation, path, options=None, **kwargs):
    return invoke('work.'+operation, arguments={'work_dir': str(path)}, options=options, **kwargs)


def complete_public(path, **kwargs):
    status = work('status', path)
    assert status.exit_code == 0, status.as_dict()
    for _ in range(status.result['data']['progress']['total_units']+2):
        result = work('resume', path, **kwargs)
        if result.exit_code != 8:
            return result
    raise AssertionError('Public finite Proposal Work did not complete')
