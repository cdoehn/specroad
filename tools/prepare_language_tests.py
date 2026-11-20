"""Explicit local setup from existing managed interpreters and offline wheels.

No downloads, installations, product tests or service actions. This operator
command inspects only the explicitly selected interpreter directory.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

if __name__ == '__main__':
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from language_packaging.inventory import NUMPY
from language_packaging.wheels import read_wheels, regular_bytes
from language_packaging.runtime_matrix import load_runtime_matrix


def prepare(python_directory, wheelhouse, output):
    python_directory = Path(python_directory).resolve(strict=True)
    wheelhouse = Path(wheelhouse).resolve(strict=True)
    output = Path(output).absolute()
    if output.exists():
        raise FileExistsError('Existing runtime configuration is preserved')
    rows = {}
    code = 'import json,platform,sys,sysconfig;print(json.dumps([sys.implementation.name,platform.python_version(),sys.platform,platform.machine(),bool(sysconfig.get_config_var("Py_GIL_DISABLED"))]))'
    for minor in NUMPY:
        candidates = list(python_directory.glob('cpython-' + minor + '.*-linux-x86_64-gnu/bin/python' + minor))
        if len(candidates) != 1:
            raise ValueError('Select exactly one prepared standard CPython for ' + minor)
        interpreter = candidates[0].resolve(strict=True)
        before = sha256(regular_bytes(interpreter)).hexdigest()
        result = subprocess.run([str(interpreter), '-I', '-B', '-c', code],
            stdin=subprocess.DEVNULL, capture_output=True, check=True,
            env={'PATH':os.defpath, 'LANG':'C.UTF-8'})
        implementation, version, system, machine, free_threaded = json.loads(result.stdout)
        if (implementation != 'cpython' or not version.startswith(minor + '.') or system != 'linux'
                or machine != 'x86_64' or free_threaded or sha256(regular_bytes(interpreter)).hexdigest() != before):
            raise ValueError('Interpreter identity differs from selected runtime')
        read_wheels(wheelhouse, minor)
        rows[minor] = dict(executable=str(interpreter), version=version, sha256=before)
    value = dict(format_version=1, kind='specroad-language-test-runtimes-v1',
                 wheelhouse=str(wheelhouse), interpreters=rows)
    if any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError('Linked runtime configuration output')
    # No replacement and no activation of a service; the operator selects output.
    with output.open('xb') as stream:
        stream.write((json.dumps(value, indent=2, sort_keys=True) + '\n').encode())
        stream.flush(); os.fsync(stream.fileno())
    assert load_runtime_matrix(output) == value
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python-directory', required=True, type=Path)
    parser.add_argument('--wheelhouse', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    value = prepare(args.python_directory, args.wheelhouse, args.output)
    print(json.dumps(dict(prepared=True, interpreters={k:v['version'] for k,v in value['interpreters'].items()}, tests_run=0)))


if __name__ == '__main__':
    main()
