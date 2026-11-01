"""Prepare real file states and a private entrypoint; never run tests or Git."""
import base64
from hashlib import sha256
from pathlib import Path
import shlex
import zlib

from .bundle_apply import canonical, validate_bundle
from .commit_tests import validate_plan
from .identity import source_identity


def prepare_stage(before, after, paths, *, commit_id, message, test_plan):
    before, after = Path(before), Path(after)
    paths = sorted(set(paths))
    plan = dict(test_plan, commit_id=commit_id)
    changed_tests = {p for p in paths if p.startswith('tests/') and Path(p).name.startswith('test_')
                     and p.endswith('.py')}
    plan['test_files'] = sorted(set(plan['test_files']) | changed_tests)
    validate_plan(plan, commit_id)
    prior, payloads, final = {}, {}, {}
    for name in paths:
        path = after / name
        if not path.is_file() or path.is_symlink():
            raise ValueError('Stage v1 requires a regular final file: ' + name)
        raw = path.read_bytes()
        payloads[name] = base64.b64encode(raw).decode()
        final[name] = sha256(raw).hexdigest()
        old = before / name
        if old.exists():
            if not old.is_file() or old.is_symlink():
                raise ValueError('Stage v1 requires a regular preimage: ' + name)
            prior[name] = sha256(old.read_bytes()).hexdigest()
    return {'commit_id': commit_id, 'message': message, 'before': prior, 'after': final,
            'payloads': payloads, 'source_sha256': source_identity(after), 'test_plan': plan}


def render_entrypoint(data, *, core_python):
    validate_bundle(data)
    for stage in data['stages']:
        validate_plan(stage['test_plan'], stage['commit_id'])
    if not Path(core_python).is_absolute() or '\n' in str(core_python):
        raise ValueError('An explicit installed PatchHarbor interpreter is required')
    driver = Path(__file__).with_name('bundle_apply.py').read_text()
    packed = base64.b64encode(zlib.compress(canonical(data), 9)).decode()
    program = (driver + '\nimport zlib\nDATA = json.loads(zlib.decompress(base64.b64decode('
               + repr(packed) + ')))\n'
               'try:\n    run_bundle(DATA, NativeApply(DATA))\n'
               'except Exception as error:\n'
               '    print("Apply failed; completed commits and current files/index are retained: " + str(error), file=sys.stderr, flush=True)\n'
               '    for captured in (getattr(error, "stdout", None), getattr(error, "stderr", None)):\n'
               '        if captured: print(captured.decode(errors="replace") if isinstance(captured, bytes) else str(captured), file=sys.stderr, flush=True)\n'
               '    raise SystemExit(1)\n'
               'print("PATCHHARBOR-BUNDLE-NR: " + DATA["bundle_number"] + " | APPLIED SUCCESSFULLY", flush=True)\n')
    return ('#!/usr/bin/env bash\n# PATCHHARBOR\nset -euo pipefail\nexec '
            + shlex.quote(str(core_python)) + " -I -B - <<'SPECROAD_APPLY_COMMIT_PLAN'\n"
            + program + 'SPECROAD_APPLY_COMMIT_PLAN\n').encode()
