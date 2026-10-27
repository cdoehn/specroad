"""Closed Restore request grammar, without filesystem or authority effects."""
import builtins
from contextlib import contextmanager, ExitStack
import io
import os
from unittest.mock import patch

import pytest

from specroad.cli._restore_options import restore_request
from specroad.cli.requests import CommandRequest
from specroad.recovery import RestoreError
from support.read_only import no_write_attempts


PLAN = {'--project': '/not-opened/project', '--from': 'source.zip',
    '--source-root': '/not-opened/source', '--source-kind': 'project_bundle',
    '--dry-run': True, '--output-root': '/not-opened/output', '--output': 'plan.json'}
EXECUTE = {'--project': '/not-opened/project', '--plan-root': '/not-opened/input',
    '--plan': 'plan.json', '--expected-target-root': 'a' * 64,
    '--actor-type': 'human', '--actor-id': 'synthetic-operator'}


@contextmanager
def no_io_attempts():
    calls = []
    def forbid(*args, **kwargs):
        calls.append(args)
        raise AssertionError('Restore argument binding must not inspect files')
    with no_write_attempts(), ExitStack() as stack:
        for module, name in ((builtins, 'open'), (io, 'open'), (os, 'open'),
                             (os, 'stat'), (os, 'lstat'), (os, 'scandir'),
                             (os, 'listdir'), (os, 'readlink')):
            stack.enter_context(patch.object(module, name, forbid))
        yield
    assert not calls


def invocation(options, representation):
    if representation == 'argv':
        words = ['recover', 'restore']
        for flag, value in options.items():
            words.extend([flag] if value is True else [flag, value])
        return words
    return {'command_id': 'recover.restore', 'options': options}


def reject(value, code=2):
    with no_io_attempts(), pytest.raises(RestoreError) as error:
        restore_request(value)
    assert error.value.exit_code == code
    assert not error.value.mutation_possible and not error.value.recovery_required


@pytest.mark.parametrize('options', [PLAN, EXECUTE])
def test_argv_mapping_and_owned_request_have_identical_fresh_parameters(options):
    with no_io_attempts():
        argv = restore_request(invocation(options, 'argv'))
        source = invocation(dict(options), 'mapping')
        structured = restore_request(source)
        owned = restore_request(CommandRequest('recover.restore', options))
    assert argv.as_dict() == structured.as_dict() == owned.as_dict()
    source['options']['--project'] = '/other'
    assert structured.options['--project'] == options['--project']


@pytest.mark.parametrize('representation', ['argv', 'mapping'])
@pytest.mark.parametrize('mode,missing', [('plan', flag) for flag in PLAN]
                         + [('execute', flag) for flag in EXECUTE])
def test_every_explicit_required_option_is_required_before_io(representation, mode, missing):
    options = dict(PLAN if mode == 'plan' else EXECUTE)
    del options[missing]
    reject(invocation(options, representation))


@pytest.mark.parametrize('representation', ['argv', 'mapping'])
@pytest.mark.parametrize('mode,extra', [('plan', {k: v}) for k, v in EXECUTE.items() if k != '--project']
    + [('execute', {k: v}) for k, v in PLAN.items() if k != '--project']
    + [('plan', {'--selection-root': '/selection', '--affected-journals': 'selection.json'}),
       ('plan', {'--request-id': 'request'}), ('plan', {'--force': True}),
       ('plan', {'--expected-lock-sha256': 'b' * 64}), ('plan', {'--reason': 'reason'}),
       ('plan', {'--accept-remote-risk': True}), ('execute', {'--default-locale': 'en-GB'}),
       ('execute', {'--generated-path': 'generated'}), ('plan', {'--as-proposal': True})])
def test_modes_do_not_borrow_options(representation, mode, extra):
    reject(invocation({**(PLAN if mode == 'plan' else EXECUTE), **extra}, representation))


@pytest.mark.parametrize('representation', ['argv', 'mapping'])
@pytest.mark.parametrize('kind,extra,valid', [
    ('baseline', {}, False), ('baseline', {'--default-locale': 'en-GB'}, False),
    ('baseline', {'--generated-path': 'output'}, False),
    ('baseline', {'--default-locale': 'en-GB', '--generated-path': 'output'}, True),
    ('project_bundle', {'--default-locale': 'en-GB'}, False),
    ('project_bundle', {'--generated-path': 'output'}, False),
    ('project_bundle', {'--default-locale': 'en-GB', '--generated-path': 'output'}, False),
    ('auto', {}, False)])
def test_source_kind_and_operational_values_are_explicit(representation, kind, extra, valid):
    value = invocation({**PLAN, '--source-kind': kind, **extra}, representation)
    if valid:
        with no_io_attempts():
            request = restore_request(value)
        assert request.options['--generated-path'] == 'output'
    else:
        reject(value)


@pytest.mark.parametrize('actor', ['human', 'tool', 'ai', 'ci'])
@pytest.mark.parametrize('request_id', [None, 'explicit-request'])
def test_actor_request_id_requirement_is_shared_with_native_restore(actor, request_id):
    options = {**EXECUTE, '--actor-type': actor}
    if request_id is not None:
        options['--request-id'] = request_id
    value = invocation(options, 'mapping')
    if actor in ('ai', 'ci') and request_id is None:
        reject(value)
    else:
        with no_io_attempts():
            request = restore_request(value)
        assert request.options.get('--request-id') == request_id


@pytest.mark.parametrize('extra,valid', [
    ({'--selection-root': '/selection'}, False), ({'--affected-journals': 'selection.json'}, False),
    ({'--selection-root': '/selection', '--affected-journals': 'selection.json'}, True),
    ({'--force': True}, False), ({'--expected-lock-sha256': 'b' * 64}, False),
    ({'--reason': 'explicit recovery'}, False), ({'--accept-remote-risk': True}, False),
    ({'--force': True, '--expected-lock-sha256': 'b' * 64, '--reason': 'explicit recovery'}, True),
    ({'--force': True, '--expected-lock-sha256': 'b' * 64, '--reason': 'explicit recovery',
      '--accept-remote-risk': True}, True)])
def test_selection_and_owner_takeover_parameters_never_fill_missing_partners(extra, valid):
    value = invocation({**EXECUTE, **extra}, 'mapping')
    if valid:
        with no_io_attempts():
            result = restore_request(value)
        assert all(result.options[k] == v for k, v in extra.items())
    else:
        reject(value)


@pytest.mark.parametrize('extra', [
    {'--expected-target-root': 'A' * 64}, {'--expected-target-root': 'a' * 63},
    {'--expected-target-root': True}, {'--actor-type': 'admin'}, {'--actor-id': ''},
    {'--actor-id': '\x00'}, {'--actor-id': '\ud800'}, {'--actor-id': False},
    {'--actor-id': 1}, {'--actor-id': ['same', 'same']}, {'--request-id': []},
    {'--force': False}, {'--force': 'true'}, {'--dry-run': True},
    {'--authority': 'allow'}, {'--resolved-project': '/other'}, {'--profile': 'saved'}])
def test_invalid_scalar_flags_or_untrusted_context_are_rejected(extra):
    reject(invocation({**EXECUTE, **extra}, 'mapping'))


@pytest.mark.parametrize('value', [None, {}, {'command_id': 'recover.status', 'options': EXECUTE},
    {'command_id': 'recover.restore', 'options': EXECUTE, 'resolved': {}},
    {'command_id': 'recover.restore', 'options': EXECUTE, 'authority': 'allow'},
    {'command_id': 'recover.restore', 'options': EXECUTE, 'arguments': {'file': 'plan.json'}},
    [], ['recover', 'restore', 1], ['recover', 'restore', '\0']])
def test_only_closed_request_data_or_real_argv_are_accepted(value):
    reject(value)


@pytest.mark.parametrize('tail', [['--project', '/other'], ['--dry-run'], ['surplus'], ['--from=other']])
def test_argv_repetition_and_extra_arguments_are_rejected(tail):
    reject(invocation(PLAN, 'argv') + tail)


@pytest.mark.parametrize('mode,flag', [('plan', '--project'), ('plan', '--source-root'),
    ('plan', '--output-root'), ('execute', '--plan-root')])
@pytest.mark.parametrize('path', ['relative', '/root/../other', '/root//child', '/root/'])
def test_noncanonical_roots_are_not_normalized_or_resolved(mode, flag, path):
    reject(invocation({**(PLAN if mode == 'plan' else EXECUTE), flag: path}, 'mapping'), 7)


@pytest.mark.parametrize('mode,flag', [('plan', '--from'), ('plan', '--output'), ('execute', '--plan')])
@pytest.mark.parametrize('path', ['/absolute', '../outside', 'a/../outside', 'bad\\path'])
def test_file_values_are_relative_safe_paths(mode, flag, path):
    reject(invocation({**(PLAN if mode == 'plan' else EXECUTE), flag: path}, 'mapping'), 7)
