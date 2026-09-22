"""Behavior regressions for supported runtimes, not version-specific skips."""
import builtins
import copy
import json
from contextlib import contextmanager
from unittest.mock import Mock, patch

import pytest

from specroad.srx import MISSING, SrxError, value_type
from specroad.storage.metadata import ArtifactMetadata, serialize_common_artifact
from specroad.storage.json_syntax import parse_json_object
from support.artifacts import common_artifact


@contextmanager
def block_imports_and_open():
    """Resolve targets and replacements before blocking imports themselves."""
    imports = Mock(side_effect=AssertionError("Unexpected import"))
    files = Mock(side_effect=AssertionError("Unexpected file access"))
    with patch.object(builtins, "open", files), patch.object(builtins, "__import__", imports):
        yield


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
