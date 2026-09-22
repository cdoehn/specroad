"""Behavior regressions for supported runtimes, not version-specific skips."""
import builtins
import copy
import json
from unittest.mock import Mock, patch

import pytest

from specroad.srx import MISSING, SrxError, value_type
from specroad.storage.metadata import ArtifactMetadata, serialize_common_artifact
from specroad.storage.json_syntax import parse_json_object
from support.artifacts import common_artifact
from support.io_guards import block_imports_and_open




def test_missing_copy_keeps_identity_inside_owned_containers():
    shared = [MISSING, {"absent": MISSING, "null": None}]
    original = {"first": shared, "second": shared}
    clone = copy.deepcopy(original)
    assert clone is not original and clone["first"] is not shared
    assert clone["first"] is clone["second"]
    assert clone["first"][0] is MISSING
    assert clone["first"][1]["absent"] is MISSING
    assert clone["first"][1]["null"] is None
    clone["first"].append(42)
    assert len(shared) == 2


def test_guard_denies_real_import_and_open_calls():
    with block_imports_and_open():
        for operation in (lambda: __import__("os"), lambda: open("not-opened.json")):
            try:
                operation()
            except AssertionError:
                pass
            else:
                raise AssertionError("Guard failed to reject an I/O attempt")


def test_guarded_metadata_roundtrip_still_processes_passive_data():
    value = common_artifact(extensions={"uninstalled.plugin": {
        "entrypoint": "os.system", "command": "raise", "payload": [None, False, 3]}})
    original = copy.deepcopy(value)
    with block_imports_and_open():
        projected = ArtifactMetadata(value).data
        encoded = serialize_common_artifact(value)
    assert projected["extensions"] == original["extensions"]
    assert parse_json_object(encoded) == original
    assert value == original


def test_missing_deepcopy_preserves_cycles_and_aliases():
    original = [MISSING]
    original.append(original)
    clone = copy.deepcopy(original)
    assert clone is not original
    assert clone[0] is MISSING and clone[1] is clone
    assert original[1] is original


def test_missing_as_mapping_key_keeps_identity_and_existing_memo_entries():
    unrelated = object()
    memo = {id(unrelated): unrelated}
    clone = copy.deepcopy({MISSING: [MISSING]}, memo)
    assert list(clone)[0] is MISSING and clone[MISSING][0] is MISSING
    assert memo[id(unrelated)] is unrelated


def test_copied_missing_is_not_null_boolean_or_serializable_json():
    for copier in (copy.copy, copy.deepcopy):
        value = copier(MISSING)
        assert value is MISSING and value is not None
        assert value_type(value) == "missing"
        with pytest.raises(TypeError):
            bool(value)
        with pytest.raises(TypeError):
            json.dumps(value)
        with pytest.raises(SrxError):
            value_type({"nested": value})


def test_missing_copy_does_not_depend_on_newer_enum_copy_helpers(tmp_path):
    from support.processes import run_core
    result = run_core("""
import copy
from enum import Enum
# An isolated process models the absent base helpers of CPython 3.10.
# Never change the pytest worker's Enum class or global dispatch registries.
for name in ('__copy__', '__deepcopy__'):
    if name in Enum.__dict__:
        delattr(Enum, name)
from specroad.srx import MISSING
assert copy.copy(MISSING) is MISSING
assert copy.deepcopy(MISSING) is MISSING
assert copy.deepcopy({'x': [MISSING]})['x'][0] is MISSING
""", tmp_path)
    assert result.returncode == 0, result.stderr


def test_guard_restores_builtins_after_protected_body_raises():
    original_import, original_open = builtins.__import__, builtins.open
    class InjectedFailure(RuntimeError):
        pass
    with pytest.raises(InjectedFailure):
        with block_imports_and_open():
            raise InjectedFailure()
    assert builtins.__import__ is original_import
    assert builtins.open is original_open


def test_guard_restores_nested_outer_replacements():
    outer_import = Mock(wraps=builtins.__import__)
    outer_open = Mock(wraps=builtins.open)
    with patch.object(builtins, "open", outer_open), patch.object(builtins, "__import__", outer_import):
        with block_imports_and_open():
            assert builtins.__import__ is not outer_import
            assert builtins.open is not outer_open
        assert builtins.__import__ is outer_import and builtins.open is outer_open
    outer_import.assert_not_called()
    outer_open.assert_not_called()


def test_invalid_metadata_does_not_bypass_guard_or_change_input():
    from specroad.model.errors import ModelError
    value = common_artifact(extensions={"invalid_namespace": {"command": "ignored"}})
    before = copy.deepcopy(value)
    rejected = False
    with block_imports_and_open():
        try:
            ArtifactMetadata(value)
        except ModelError:
            rejected = True
    assert rejected and value == before


def test_guard_can_be_nested_without_reimporting_targets():
    original_import, original_open = builtins.__import__, builtins.open
    with block_imports_and_open():
        first_import, first_open = builtins.__import__, builtins.open
        with block_imports_and_open():
            assert builtins.__import__ is not first_import
            assert builtins.open is not first_open
        assert builtins.__import__ is first_import and builtins.open is first_open
    assert builtins.__import__ is original_import and builtins.open is original_open


def test_portable_missing_copy_preserves_identity(tmp_path):
    from support.portable import build_distribution, files_under
    from support.processes import run_python
    target = tmp_path / "built"
    build_distribution(target)
    moved = tmp_path / "relocated"
    target.rename(moved)
    before = files_under(moved)
    code = """
import copy
from specroad.srx import MISSING, value_type
for copier in (copy.copy, copy.deepcopy):
    assert copier(MISSING) is MISSING
assert copy.deepcopy([{'x': MISSING}])[0]['x'] is MISSING
assert value_type(copy.deepcopy(MISSING)) == 'missing'
"""
    for location in (moved / "module", moved / "specroad.pyz"):
        result = run_python(['-I', '-S', '-B', '-c',
                             'import sys;sys.path.insert(0,' + repr(str(location)) + ');\n' + code], tmp_path)
        assert result.returncode == 0, result.stderr
    assert files_under(moved) == before
