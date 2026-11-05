"""Timeout adapter for the installed native Watcher; no new scheduler or Apply loop."""
import argparse
from functools import partial
import json
from pathlib import Path
import sys


def timeout_value(raw):
    try:
        value = int(raw)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError('timeout must be a positive whole number of seconds') from None
    if str(value) != str(raw) or value <= 0 or value > 2147483647:
        raise argparse.ArgumentTypeError('timeout must be a positive bounded whole number of seconds')
    return value


def worker(timeout, request, *, api, decode_scope, progress_document, stdout, stderr):
    """One native apply_next call; retain the native scoped JSON/error protocol."""
    timeout = timeout_value(timeout)
    entries = decode_scope(request)
    options = {'timeout': timeout}
    if entries is not None:
        options['exchanges'] = tuple(api.ExchangeWatchTarget(
            Path(entry['directory']), entry['device'], entry['inode'],
            tuple(api.RepositoryId(value) for value in entry['repository_ids'])) for entry in entries)
    report = api.apply_next(**options)
    document = dict(report.apply_json_envelope())
    document['watcher_progress'] = progress_document(report.automatic)
    stdout.write(json.dumps(document, ensure_ascii=True, allow_nan=False, separators=(',', ':')) + '\n')
    stdout.flush()
    if report.result_bundle.status is api.ResultBundleStatus.FAILED:
        diagnostics = report.result_bundle.emergency_diagnostics_path
        message = ('patchharbor: emergency diagnostics: ' + json.dumps(str(diagnostics), ensure_ascii=True)
                   if diagnostics is not None else 'patchharbor: Result publication failed; no emergency diagnostics path')
        stderr.write(message + '\n'); stderr.flush()
    return report.process_exit_code


def delegate_for(timeout, delegate):
    command = (sys.executable, '-I', '-B', str(Path(__file__).resolve()),
               '--worker', '--timeout', str(timeout_value(timeout)))
    return partial(delegate, apply_command=command)


def main(argv=None, *, stdout=None, stderr=None):
    parser = argparse.ArgumentParser(description='Native PatchHarbor Watcher with an explicit Apply timeout.', allow_abbrev=False)
    parser.add_argument('--timeout', type=timeout_value, default=10800, help='Apply timeout in seconds (default: 10800)')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    import patchharbor.api as api
    if args.worker:
        from patchharbor_watcher.protocol import MAX_REQUEST_BYTES, decode_scope, progress_document
        return worker(args.timeout, sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1), api=api,
                      decode_scope=decode_scope, progress_document=progress_document, stdout=stdout, stderr=stderr)
    from patchharbor_watcher.apply_boundary import delegate_to_automatic_apply
    from patchharbor_watcher.lifecycle import WatcherStopController, installed_stop_signals
    from patchharbor_watcher.loop import run_repository_watcher
    controller = WatcherStopController()
    try:
        api.repositories()
        with installed_stop_signals(controller):
            run_repository_watcher(delegate=delegate_for(args.timeout, delegate_to_automatic_apply),
                                   log_stream=stdout, error_stream=stderr,
                                   stop_requested=controller.stop_requested, bind_wake=controller.bind_wake)
    except KeyboardInterrupt:
        return 130
    except (api.PatchHarborError, OSError, RuntimeError, ValueError) as error:
        print('patchharbor-watcher: ' + str(error), file=stderr)
        return 1
    return 130 if controller.was_interrupted() else 0


if __name__ == '__main__':
    raise SystemExit(main())
