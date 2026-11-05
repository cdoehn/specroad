"""Keep native failures and protocol boundaries when forwarding timeout values."""
import argparse
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from specroad_control.watcher import timeout_value, worker


@pytest.mark.parametrize('value', [0, -1, True, False, '0', '-10', '3.5', '', None, 'NaN', 'Infinity', 2147483648])
def test_bad_timeout_is_rejected_before_native_poll(value):
    native = SimpleNamespace(apply_next=Mock()); decode = Mock()
    with pytest.raises(argparse.ArgumentTypeError):
        worker(value, b'', api=native, decode_scope=decode, progress_document=Mock(), stdout=StringIO(), stderr=StringIO())
    decode.assert_not_called(); native.apply_next.assert_not_called()


@pytest.mark.parametrize('value', [1, 10800, 21600, 2147483647])
def test_positive_timeout_bounds_remain_exact(value):
    assert timeout_value(value) == value
    assert timeout_value(str(value)) == value


@pytest.mark.parametrize('diagnostics', [None, Path('/synthetic/diagnose-ä.json')])
def test_native_publication_failure_keeps_exit_and_stderr(diagnostics):
    failure = object()
    report = SimpleNamespace(apply_json_envelope=lambda: {'success': False}, automatic=None,
        result_bundle=SimpleNamespace(status=failure, emergency_diagnostics_path=diagnostics), process_exit_code=124)
    native = SimpleNamespace(apply_next=Mock(return_value=report), ResultBundleStatus=SimpleNamespace(FAILED=failure))
    stdout, stderr = StringIO(), StringIO()
    assert worker(21600, b'', api=native, decode_scope=lambda _: None,
                  progress_document=lambda _: None, stdout=stdout, stderr=stderr) == 124
    assert 'false' in stdout.getvalue() and 'diagnostics' in stderr.getvalue()
    assert stderr.getvalue().isascii()


def test_invalid_scope_never_starts_native_apply():
    native = SimpleNamespace(apply_next=Mock())
    with pytest.raises(ValueError, match='invalid scope'):
        worker(21600, b'broken', api=native, decode_scope=Mock(side_effect=ValueError('invalid scope')),
               progress_document=Mock(), stdout=StringIO(), stderr=StringIO())
    native.apply_next.assert_not_called()


def test_unexpected_native_failure_propagates_without_success_json_or_retry():
    native = SimpleNamespace(apply_next=Mock(side_effect=RuntimeError('native failure')))
    stdout = StringIO()
    with pytest.raises(RuntimeError, match='native failure'):
        worker(21600, b'', api=native, decode_scope=lambda _: None,
               progress_document=Mock(), stdout=stdout, stderr=StringIO())
    native.apply_next.assert_called_once_with(timeout=21600)
    assert stdout.getvalue() == ''
