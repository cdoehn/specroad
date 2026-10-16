"""Actual Baseline Work process loss, using the original native writer.

The child owns its project and stops only after the selected native operation.
These are process-loss observations, not power-loss or cross-platform proofs.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from specroad import _build
from specroad.changes import committing
from specroad.work import publication
from support.native_boundaries import CRASH_EXIT
from test_baseline_work_right import work_setup, ready, publish, retained_hashes

CUTS = ('prepared', 'first_object', 'baseline_record', 'committed', 'cleanup')


def writer(folder, cut):
    _build.BUILD_METADATA = {'format_version': 1,
        'hash_algorithm': 'specroad-dev-payload-v1', 'build_sha256': '4' * 64}
    root, model, plan, store, arguments = work_setup(folder, with_history=True)
    point = ready(store, arguments)
    initial = store._initial
    print(json.dumps({'pid': os.getpid(), 'initial': initial.raw.hex(),
        'initial_objects': {p: b.hex() for p, b in initial.objects.items()},
        'checkpoint': point.raw.hex(), 'plan': plan.source_bytes.hex(),
        'configuration': model.configuration_bytes.hex(),
        'documents': {d.path: d.content.hex() for d in model.documents},
        'resources': {d.path: d.content.hex() for d in model.resource_files},
        'retained': retained_hashes(root, model)}), flush=True)
    assert cut in CUTS

    def stop():
        print(json.dumps({'pid': os.getpid(), 'cut': cut}), flush=True)
        os._exit(CRASH_EXIT)

    if cut in ('first_object', 'baseline_record'):
        native = publication.publish_prepared_journal
        replace = committing.replace_bound_image

        def replace_then_stop(*args, **kwargs):
            result = replace(*args, **kwargs)
            name = args[3]
            if ((cut == 'first_object' and len(name) == 64) or
                    (cut == 'baseline_record' and name.startswith('SR-BASE-'))):
                stop()
            return result

        def interrupt(*args, **kwargs):
            with patch.object(committing, 'replace_bound_image', replace_then_stop):
                return native(*args, **kwargs)
        name = 'publish_prepared_journal'
    else:
        name = {'prepared': 'stage_building_journal', 'committed': 'finalize_committing_journal',
                'cleanup': 'cleanup_completed_transaction'}[cut]
        native = getattr(publication, name)

        def interrupt(*args, **kwargs):
            native(*args, **kwargs)
            stop()

    with patch.object(publication, name, interrupt):
        publish(store, arguments)
    raise AssertionError('Selected native Baseline phase was not reached')


def child(folder, cut):
    repository = Path(__file__).resolve().parents[2]
    bootstrap = '''import sys
from pathlib import Path
sys.path[:0] = [str(Path(sys.argv[1])/p) for p in ('src', 'tests')]
from support.baseline_work_process import writer
writer(Path(sys.argv[2]), sys.argv[3])
'''
    result = subprocess.run([sys.executable, '-I', '-B', '-c', bootstrap,
        str(repository), str(folder), cut], stdin=subprocess.DEVNULL,
        capture_output=True, text=True, check=False)
    assert result.returncode == CRASH_EXIT, (cut, result.returncode, result.stdout, result.stderr)
    return [json.loads(line) for line in result.stdout.splitlines()]
