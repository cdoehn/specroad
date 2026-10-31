"""Optional Jython absence and strict foreign-import denial in fresh processes."""

import json

import pytest

from support.import_guards import CORE_STDLIB_IMPORT_GUARD
from support.processes import run_core


@pytest.mark.parametrize('shape', ['absent', 'module', 'package'])
def test_optional_jython_probe_cannot_load_available_foreign_code(tmp_path, shape):
    marker = tmp_path / 'foreign-code-ran'
    poison = 'open(' + repr(str(marker)) + ', "w").write("executed")\n'
    if shape == 'module':
        (tmp_path / 'org.py').write_text(poison)
    elif shape == 'package':
        (tmp_path / 'org').mkdir()
        (tmp_path / 'org' / '__init__.py').write_text(poison)
    body = CORE_STDLIB_IMPORT_GUARD + '''
import json
try:
    from org.python.core import PyStringMap
except ImportError as error:
    assert isinstance(error, ModuleNotFoundError) and error.name == 'org'
    PyStringMap = None
else:
    raise AssertionError('foreign Jython code was admitted')
from copy import deepcopy
from dataclasses import dataclass
from specroad.verification import read_code_reference
original = {'nested': [1]}
copied = deepcopy(original)
copied['nested'].append(2)
assert original == {'nested': [1]} and copied == {'nested': [1, 2]}
assert not any(name == 'org' or name.startswith('org.') for name in sys.modules)
print(json.dumps({'optional_module_absent': PyStringMap is None}))
'''
    result = run_core(body, tmp_path, expose_cwd=True, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'optional_module_absent': True}
    assert not marker.exists()


@pytest.mark.parametrize('name', ['thirdparty_guard_probe', 'organization_probe'])
@pytest.mark.parametrize('present', [False, True])
def test_other_foreign_imports_cannot_be_hidden_by_importerror_handlers(tmp_path, name, present):
    marker = tmp_path / 'foreign-code-ran'
    if present:
        (tmp_path / (name + '.py')).write_text(
            'open(' + repr(str(marker)) + ', "w").write("executed")\n')
    body = CORE_STDLIB_IMPORT_GUARD + 'module_name = ' + repr(name) + '\n' + '''
import json
try:
    try:
        __import__(module_name)
    except ImportError:
        raise RuntimeError('foreign import was silently treated as optional')
except AssertionError:
    print(json.dumps({'foreign_import_blocked': True}))
else:
    raise RuntimeError('foreign import was admitted')
'''
    result = run_core(body, tmp_path, expose_cwd=True, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'foreign_import_blocked': True}
    assert not marker.exists()
