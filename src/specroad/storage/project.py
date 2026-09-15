"""Explicit resource reads under one fixed project root.

This is not yet the full inventory/closure engine. Attachments and archives need
an explicit reference; unreferenced bytes never become model input merely by
being present. Checks here authorize paths, not transactions or actual writes.
"""

import json
import os
import stat
from types import MappingProxyType

from ..model.configuration import ProjectConfiguration
from ..model.paths import CURRENT_JSON_CLASSES, PAYLOAD_CLASSES, classify_path, project_path
from ..model.errors import ModelError
from ..model.numbers import number_from_token
from ..security import ProjectBoundary


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ModelError("duplicate_key")
        result[key] = value
    return result


def _constant(value):
    raise ModelError("nonfinite_number")


class ProjectSource:
    def __init__(self, root, *, expected_project_id=None):
        self.boundary = ProjectBoundary(root)
        self.configuration_bytes = self.boundary.read_bytes("specroad.json")
        try:
            value = json.loads(self.configuration_bytes.decode("utf-8"),
                               object_pairs_hook=_unique, parse_constant=_constant,
                               parse_int=number_from_token, parse_float=number_from_token)
        except (ValueError, UnicodeError, RecursionError) as error:
            if isinstance(error, ModelError):
                raise
            raise ModelError("invalid_json", path="specroad.json") from error
        self.configuration = ProjectConfiguration(value)
        if expected_project_id is not None and self.configuration.project_id != expected_project_id:
            raise ModelError("project_identity_mismatch")

    def _fresh_configuration(self):
        if self.boundary.read_bytes("specroad.json") != self.configuration_bytes:
            raise ModelError("configuration_changed", path="specroad.json")

    @staticmethod
    def _paths(values):
        if isinstance(values, (str, bytes)):
            raise ModelError("path_sequence_required")
        try:
            result = tuple(project_path(name) for name in values)
        except TypeError as error:
            raise ModelError("path_sequence_required") from error
        if len(set(result)) != len(result):
            raise ModelError("duplicate_resource_path")
        return result

    def classify(self, path):
        return classify_path(path, self.configuration)

    def read_normative(self, path, *, referenced_payloads=()):
        self._fresh_configuration()
        referenced_payloads = self._paths(referenced_payloads)
        kind = self.classify(path)
        if kind not in CURRENT_JSON_CLASSES and not (kind in PAYLOAD_CLASSES and path in referenced_payloads):
            raise ModelError("not_normative_input", path=path)
        raw = self.boundary.read_bytes(path)
        if path == "specroad.json" and raw != self.configuration_bytes:
            raise ModelError("configuration_changed", path=path)
        self._fresh_configuration()
        return raw

    def load_resources(self, paths, *, referenced_payloads=()):
        """Load an explicit resource set, never a directory-wide fallback."""
        self._fresh_configuration()
        names = self._paths(paths)
        referenced_payloads = self._paths(referenced_payloads)
        loaded = {name: self.read_normative(name, referenced_payloads=referenced_payloads)
                  for name in sorted(names)}
        self._fresh_configuration()
        return MappingProxyType(loaded)

    def require_write_target(self, path):
        """Preliminary authorization only; a future writer must recheck at Write.

        No file is created. This is not a reusable race-free write capability.
        """
        self._fresh_configuration()
        path = project_path(path)
        kind = self.classify(path)
        if kind not in CURRENT_JSON_CLASSES and kind not in PAYLOAD_CLASSES:
            raise ModelError("outside_managed_paths", path=path)
        cursor = self.boundary.root
        parts = path.split("/")
        for index, part in enumerate(parts):
            cursor = cursor / part
            try:
                info = cursor.lstat()
            except FileNotFoundError:
                break
            directory = index < len(parts) - 1
            wanted = stat.S_ISDIR if directory else stat.S_ISREG
            if stat.S_ISLNK(info.st_mode) or not wanted(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
                raise ModelError("unsafe_write_target", path=path)
            if directory and os.path.lexists(cursor / "specroad.json"):
                raise ModelError("foreign_project_root", path=path)
        self._fresh_configuration()
        return kind
