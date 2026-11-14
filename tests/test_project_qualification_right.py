"""Common reader safety, unknown formats and invocation-local original checks."""
import os

import pytest

from specroad.model.canonical import canonical_json_bytes
from specroad.qualification import QualificationError
from specroad.qualification.inventory import boundary, observe, read_source
from specroad.qualification.project import validate_project
from specroad.qualification.owned import owned_checks
from specroad.security import SafetyViolation
from support.model import put
from support.read_only import inventory, no_write_attempts
from test_proposal_basis import project


@pytest.mark.parametrize('fault', [None, 'hardlink', 'symlink', 'alias'])
def test_common_inventory_retains_no_follow_and_portable_name_guards(tmp_path, fault):
    root = tmp_path / 'project'
    root.mkdir()
    raw = b'original source'
    put(root, 'sources/input.bin', raw)
    if fault == 'hardlink':
        os.link(root / 'sources/input.bin', tmp_path / 'other-name')
    elif fault == 'symlink':
        (root / 'sources/input.bin').unlink()
        put(tmp_path, 'external.bin', raw)
        (root / 'sources/input.bin').symlink_to(tmp_path / 'external.bin')
    elif fault == 'alias':
        put(root, 'sources/INPUT.bin', raw)
    before = inventory(tmp_path)
    with no_write_attempts():
        bound = boundary(root)
        if fault is None:
            assert read_source(bound, 'sources/input.bin') == raw
            observed, files = observe(bound, ['sources'])
            assert files == {'sources/input.bin': raw}
            assert {r['path'] for r in observed['entries']} == {'sources', 'sources/input.bin'}
        else:
            for operation in (lambda: read_source(bound, 'sources/input.bin'),
                              lambda: observe(bound, ['sources'])):
                with pytest.raises((QualificationError, SafetyViolation)):
                    operation()
    assert inventory(tmp_path) == before


def test_normal_native_qualification_works_with_restore_adapters_unavailable(tmp_path):
    import base64
    import json
    from pathlib import Path
    import subprocess
    import sys
    model = project(tmp_path / 'project')
    before = inventory(tmp_path)
    program = '''
import base64, importlib.abc, json, sys
class NoRestore(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if (fullname == 'specroad.recovery' or fullname.startswith('specroad.recovery.')
                or fullname.startswith('specroad.work.restore')):
            raise AssertionError('Normal qualification requested Restore: ' + fullname)
sys.meta_path.insert(0, NoRestore())
from specroad.qualification import QualificationServices, QualificationError
from specroad.qualification.project import validate_project
from specroad.cli.invocation_context import InvocationContextBuilder
from specroad.cli.work_handler import absolute
from support.read_only import no_write_attempts
files = {p: base64.b64decode(b) for p, b in json.load(sys.stdin).items()}
with no_write_attempts():
    model, root = validate_project(files, services=QualificationServices())
    broken = dict(files)
    data = json.loads(broken['specroad.json'])
    data['schema_version'] = '999.0.0'
    broken['specroad.json'] = json.dumps(data).encode()
    try:
        validate_project(broken)
    except QualificationError as error:
        assert error.reason == 'restore_unsupported_source_schema_version'
    else:
        raise AssertionError('Unknown format accepted')
print(json.dumps({'root': root, 'files': sorted(model.source_files)}))
'''
    source_root = Path(__file__).resolve().parents[1]
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
        PYTHONPATH=os.pathsep.join(str(source_root / p) for p in ('src', 'tests')))
    result = subprocess.run([sys.executable, '-B', '-c', program], cwd=tmp_path,
        input=json.dumps({p: base64.b64encode(b).decode('ascii') for p, b in model.source_files.items()}),
        text=True, capture_output=True, env=environment)
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed['root'] == validate_project(model.source_files)[1]
    assert observed['files'] == sorted(model.source_files)
    assert inventory(tmp_path) == before


def test_common_reader_rejects_replaced_root_before_reading_foreign_bytes(tmp_path):
    root = tmp_path / 'project'
    root.mkdir()
    put(root, 'original.bin', b'original')
    bound = boundary(root)
    root.rename(tmp_path / 'retained')
    root.mkdir()
    put(root, 'original.bin', b'foreign')
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises((QualificationError, SafetyViolation)):
        read_source(bound, 'original.bin')
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('location', ['specroad.json', 'artifact', 'profile'])
def test_unknown_declared_format_is_not_healed_by_a_preceding_valid_qualification(tmp_path, location):
    import json
    model = project(tmp_path)
    files = model.source_files
    path = (location if location == 'specroad.json' else
            next(p for p in files if p.startswith('spec/' if location == 'artifact' else 'profiles/')))
    changed = json.loads(files[path])
    changed['schema_version'] = '999.0.0'
    broken = {**files, path: canonical_json_bytes(changed)}
    before = inventory(tmp_path)

    @owned_checks
    def qualify():
        validate_project(files)
        with pytest.raises(QualificationError) as error:
            validate_project(broken)
        assert error.value.reason == 'restore_unsupported_source_schema_version'
        assert error.value.path == path and error.value.pointer == '/schema_version'
        assert error.value.exit_code == 3
        validate_project(files)

    with no_write_attempts():
        qualify()
    assert inventory(tmp_path) == before
