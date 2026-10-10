"""Real build/process helpers for command parity across fresh runtimes.

Only test-owned code is passed as body. This is neither a product runner nor
execution authority for project or Work data. Keep assertions in the caller.
"""

import os
import subprocess
import sys


def build_core(root, output):
    return subprocess.run([sys.executable, '-I', '-B', str(root / 'tools/build_core.py'), '--output', str(output)], capture_output=True)


def process_environment():
    environment = {'PATH': ''}
    if 'LD_LIBRARY_PATH' in os.environ: environment['LD_LIBRARY_PATH'] = os.environ['LD_LIBRARY_PATH']
    return environment


def run_python(body, arguments, *, cwd, environment):
    return subprocess.run([sys.executable, '-I', '-S', '-B', '-c', body, *arguments],
        cwd=cwd, env=environment, stdin=subprocess.DEVNULL, capture_output=True)
