"""Owned subprocess cuts around the public Work/native-transaction adapter.

Every selected call performs its real native work before os._exit, without
Python exception cleanup. Build metadata is an explicit compatibility fixture,
not a measured distribution. These are process-loss tests, not power-loss tests.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from specroad import _build
from specroad.work import publication
from support.native_boundaries import CRASH_EXIT
from support.publication import TRANSACTION
from test_work_publication import setup, prepare, publish


CUTS = ('building', 'prepared', 'first_target', 'all_targets', 'committed', 'cleanup')


def writer(root, cut):
    _build.BUILD_METADATA = {'format_version': 1,
        'hash_algorithm': 'specroad-dev-payload-v1', 'build_sha256': '4' * 64}
    model, plan, preflight, reg, initial, location, store = setup(root, multi=True)
    checkpoint = prepare(store, reg, model, plan)
    if cut != 'pause_one':
        checkpoint = prepare(store, reg, model, plan)
    after = {**model.source_files, **{d.path: d.content for d in preflight.request.documents}}
    print(json.dumps({'pid': os.getpid(), 'initial': initial.raw.hex(),
        'initial_objects': {p: b.hex() for p, b in initial.objects.items()},
        'checkpoint': checkpoint.raw.hex(), 'plan': plan.source_bytes.hex(),
        'before': {p: b.hex() for p, b in model.source_files.items()},
        'after': {p: b.hex() for p, b in after.items()},
        'base_root': plan.data['base']['model_root_sha256'],
        'target_root': plan.data['expected_result']['model_root_sha256']}), flush=True)
    if cut in ('pause_one', 'pause_two'):
        return
    assert cut in CUTS

    def stop():
        print(json.dumps({'pid': os.getpid(), 'cut': cut}), flush=True)
        os._exit(CRASH_EXIT)

    if cut == 'first_target':
        native = publication.publish_prepared_journal
        native_replace = os.replace

        def replace(src, dst, **kwargs):
            result = native_replace(src, dst, **kwargs)
            if dst != 'journal.json':
                stop()
            return result

        def interrupt(*args, **kwargs):
            with patch.object(os, 'replace', replace):
                return native(*args, **kwargs)
        name = 'publish_prepared_journal'
    else:
        name = {'building': 'begin_building_journal', 'prepared': 'stage_building_journal',
            'all_targets': 'publish_prepared_journal', 'committed': 'finalize_committing_journal',
            'cleanup': 'cleanup_completed_transaction'}[cut]
        native = getattr(publication, name)

        def interrupt(*args, **kwargs):
            native(*args, **kwargs)
            stop()

    with patch.object(publication, name, interrupt):
        publish(store, reg, model, plan, transaction_id=TRANSACTION)
    raise AssertionError('Selected native phase was not reached')


def child(root, cut):
    repository = Path(__file__).resolve().parents[2]
    bootstrap = '''import sys
from pathlib import Path
sys.path[:0] = [str(Path(sys.argv[1])/p) for p in ('src', 'tests')]
from support.work_publication_process import writer
writer(Path(sys.argv[2]), sys.argv[3])
'''
    result = subprocess.run([sys.executable, '-I', '-B', '-c', bootstrap,
        str(repository), str(root), cut], stdin=subprocess.DEVNULL,
        capture_output=True, text=True, check=False)
    expected = 0 if cut.startswith('pause_') else CRASH_EXIT
    assert result.returncode == expected, (cut, result.returncode, result.stdout, result.stderr)
    return [json.loads(line) for line in result.stdout.splitlines()]
