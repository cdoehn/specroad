"""Prepare real file states and a private entrypoint; never run tests or Git."""
import base64
from hashlib import sha256
import os
from pathlib import Path, PurePosixPath
import re
import stat
import shlex
import zlib

from .bundle_apply import canonical, validate_bundle
from .commit_tests import validate_plan
from .identity import source_identity


def prepare_stage(before, after, paths, *, commit_id, message, test_plan, role=None,
                  deletion_preimages=None):
    before, after = Path(before), Path(after)
    paths = sorted(set(paths))
    plan = dict(test_plan, commit_id=commit_id)
    # Already absent targets require original bytes from the authenticated failed
    # plan. Bundle/Control validation also requires its exact correction prefix.
    deletion_preimages = {} if deletion_preimages is None else dict(deletion_preimages)
    if not set(deletion_preimages) <= set(paths):
        raise ValueError('Deletion preimage outside the prepared scope')
    changed_tests = {p for p in paths if p.startswith('tests/') and Path(p).name.startswith('test_')
                     and p.endswith('.py') and os.path.lexists(after/p)}
    plan['test_files'] = sorted(set(plan['test_files']) | changed_tests)
    validate_plan(plan, commit_id)
    prior, payloads, final, deletions, originals = {}, {}, {}, {}, {}
    for name in paths:
        relative = PurePosixPath(name)
        if (relative.is_absolute() or str(relative) != name
                or not re.fullmatch(r'[A-Za-z0-9_./-]+', name)
                or any(p.lower() in ('.', '..', '.git', '.patchharbor') for p in relative.parts)):
            raise ValueError('Unsafe stage preparation path')
        for source in (before, after):
            for parent in (source/name).parents:
                if parent.exists() or parent.is_symlink():
                    if not stat.S_ISDIR(parent.lstat().st_mode):
                        raise ValueError('Linked stage preparation parent')
        old = before / name
        old_raw = None
        if os.path.lexists(old):
            old_raw = regular_bytes(old, deletion=not os.path.lexists(after/name))
            prior[name] = sha256(old_raw).hexdigest()
        path = after / name
        if os.path.lexists(path):
            if name in deletion_preimages:
                raise ValueError('Deletion target still exists: ' + name)
            raw = regular_bytes(path)
            payloads[name] = base64.b64encode(raw).decode()
            final[name] = sha256(raw).hexdigest()
        else:
            if role not in ('implementation', 'correction'):
                raise ValueError('Deletion requires an explicit v2 implementation/correction role')
            raw = deletion_preimages.get(name, old_raw)
            if type(raw) is not bytes or old_raw is not None and raw != old_raw:
                raise ValueError('Deletion requires exact full preimage bytes: ' + name)
            deletions[name] = sha256(raw).hexdigest()
            originals[name] = base64.b64encode(raw).decode()
    if set(deletions) & set(plan['test_files']):
        raise ValueError('Removed tests cannot be selected; choose surviving regression tests')
    result = {'commit_id': commit_id, 'message': message, 'before': prior, 'after': final,
              'payloads': payloads, 'source_sha256': source_identity(after), 'test_plan': plan}
    if role is not None:
        if role not in ('clarification', 'implementation', 'correction'):
            raise ValueError('Unknown stage role')
        result['role'] = role
    if deletions:
        result.update(deletions=deletions, delete_preimages=originals)
    return result


def regular_bytes(path, *, deletion=False):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or (stat.S_IMODE(info.st_mode) != 0o644 if deletion else bool(info.st_mode & 0o7111))
                or info.st_nlink != 1 or info.st_size > 32 * 1024 * 1024):
            raise ValueError('Stage requires a bounded single-link regular 0644 file: ' + str(path))
        with os.fdopen(descriptor, 'rb', closefd=False) as stream:
            raw = stream.read(32 * 1024 * 1024 + 1)
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        if (len(raw) != info.st_size or any(getattr(info, key) != getattr(actual, key)
                for actual in (os.fstat(descriptor), path.lstat()) for key in fields)):
            raise ValueError('Stage file changed during preparation: ' + str(path))
        return raw
    finally:
        os.close(descriptor)


def render_entrypoint(data, *, core_python):
    validate_bundle(data)
    for stage in data['stages']:
        validate_plan(stage['test_plan'], stage['commit_id'])
    if not Path(core_python).is_absolute() or '\n' in str(core_python):
        raise ValueError('An explicit installed PatchHarbor interpreter is required')
    driver = Path(__file__).with_name('bundle_apply.py').read_text()
    contract = Path(__file__).with_name('bundle_contract.py').read_text()
    import_line = 'from .bundle_contract import canonical, validate_bundle, public_plan, remaining_commits, DELETION_CAPABILITY_PATH, DELETION_CAPABILITY\n'
    if driver.count(import_line) != 1:
        raise ValueError('Unexpected Apply driver imports')
    delete_import = 'from .bundle_delete import delete_bound_file\n'
    if driver.count(delete_import) != 1:
        raise ValueError('Unexpected deletion helper import')
    deletion = Path(__file__).with_name('bundle_delete.py').read_text()
    driver = contract + '\n' + deletion + '\n' + driver.replace(import_line, '', 1).replace(delete_import, '', 1)
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
