"""The isolated native worker receives the configured timeout, scope and outcomes."""
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
import json
import sys
from unittest.mock import Mock

import pytest
from specroad_control.watcher import delegate_for, worker


@pytest.mark.parametrize('entries', [None, [], [{'directory': '/synthetic/exchange', 'device': 7,
                                               'inode': 13, 'repository_ids': ['synthetic-repository']} ]])
def test_timeout_reaches_native_api_with_exact_scope_and_outcome(entries):
    native = SimpleNamespace(apply_next=Mock(), ExchangeWatchTarget=lambda *values: values,
                             RepositoryId=lambda value: ('repository', value),
                             ResultBundleStatus=SimpleNamespace(FAILED=object()))
    report = SimpleNamespace(apply_json_envelope=lambda: {'native': 'outcome'}, automatic=object(),
        result_bundle=SimpleNamespace(status=object()), process_exit_code=17)
    native.apply_next.return_value = report
    stdout, stderr = StringIO(), StringIO()
    decode = Mock(return_value=entries); progress = Mock(return_value={'native': 'progress'})
    assert worker(21600, b'scoped request', api=native, decode_scope=decode,
                  progress_document=progress, stdout=stdout, stderr=stderr) == 17
    expected = {'timeout': 21600}
    if entries is not None:
        expected['exchanges'] = tuple((Path(row['directory']), row['device'], row['inode'],
            tuple(('repository', value) for value in row['repository_ids'])) for row in entries)
    native.apply_next.assert_called_once_with(**expected)
    decode.assert_called_once_with(b'scoped request'); progress.assert_called_once_with(report.automatic)
    assert json.loads(stdout.getvalue()) == {'native': 'outcome', 'watcher_progress': {'native': 'progress'}}
    assert stderr.getvalue() == ''


def test_existing_delegate_keeps_native_process_boundary_and_explicit_timeout():
    native = Mock(return_value=object())
    delegate = delegate_for(21600, native)
    answer = delegate(exchanges=('native target',), environment={'SYNTHETIC': 'value'})
    assert answer is native.return_value
    native.assert_called_once()
    call = native.call_args.kwargs
    assert call['exchanges'] == ('native target',) and call['environment'] == {'SYNTHETIC': 'value'}
    assert call['apply_command'][:3] == (sys.executable, '-I', '-B')
    assert Path(call['apply_command'][3]).name == 'watcher.py'
    assert call['apply_command'][4:] == ('--worker', '--timeout', '21600')
