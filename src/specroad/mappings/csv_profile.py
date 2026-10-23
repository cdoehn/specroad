"""Explicit passive CSV declarations, separate from exchange mapping v1."""
from dataclasses import dataclass
from hashlib import sha256

from ..model.errors import ModelError
from ..model.metadata import validate_extensions
from ..model.versions import SCHEMA_VERSION
from ..storage.json_syntax import parse_json_object
from ._contract import (_COMMON, _array, _binding, _fail, _identity, _member,
                        _shape, _text, _unique)
from ._resources import ExchangeMapping
from ._contract import MappingError


class CSVError(MappingError):
    """Rejected conversion, with resource bindings and no copied cell values."""
    def __init__(self, reason, *, profile=None, mapping=None, source_sha256=None,
                 record=None, column=None):
        super().__init__(reason)
        self._profile = dict(profile) if profile is not None else None
        self._mapping = dict(mapping) if mapping is not None else None
        self.source_sha256 = source_sha256
        self.record = record
        self.column = column

    def diagnostic(self):
        result = super().diagnostic()
        for name, value in (("profile", self._profile), ("mapping", self._mapping),
                            ("source_sha256", self.source_sha256), ("record", self.record)):
            if value is not None:
                result[name] = dict(value) if type(value) is dict else value
        return result


def _profile(raw):
    value = parse_json_object(raw)
    _shape(value, _COMMON | {"mapping", "external_type", "identity", "columns",
                             "error_policy"}, "")
    if value["schema_version"] != SCHEMA_VERSION:
        _fail("csv_unsupported_schema")
    if value["mapping_format_version"] != "csv-profile-v1":
        _fail("csv_unsupported_profile")
    key = _identity(value)
    if _binding(value["mapping"]) == key:
        _fail("csv_resource_identity_collision")
    _text(value["external_type"], "")
    _member(value["error_policy"], ("reject",), "")
    validate_extensions(value["extensions"])
    identity = value["identity"]
    _shape(identity, {"column", "kind"}, "")
    _text(identity["column"], "")
    _member(identity["kind"], ("native_id", "external_id"), "")
    columns, fields = set(), set()
    for row in _array(value["columns"], ""):
        _shape(row, {"column", "external_field", "codec", "empty_cell", "missing_column"}, "")
        _unique(columns, _text(row["column"], ""), "")
        _unique(fields, _text(row["external_field"], ""), "")
        codec = row["codec"]
        if type(codec) is not dict:
            _fail("csv_codec_required")
        kind = codec.get("kind")
        _member(kind, ("string", "boolean", "integer", "number", "list", "typed-json-v1"), "")
        _shape(codec, {"kind", "list_rule"} if kind == "list" else {"kind"}, "")
        if kind == "list":
            _member(codec["list_rule"], ("json-array-v1",), "")
        _member(row["empty_cell"], ("value", "null", "error"), "")
        _member(row["missing_column"], ("error", "absent"), "")
        if kind == "typed-json-v1" and row["empty_cell"] != "error":
            _fail("csv_typed_empty_policy")
        if row["column"] == identity["column"] and (kind != "string" or row["empty_cell"] != "value"):
            _fail("csv_identity_column_codec")
    return value


@dataclass(frozen=True, init=False)
class CSVProfile(ExchangeMapping):
    """Owned original declaration bytes; construction alone does not select it."""
    def __init__(self, raw):
        if type(raw) is not bytes:
            raise CSVError("csv_profile_bytes_required")
        try:
            value = _profile(raw)
            self._initialize(raw, value)
        except ModelError as error:
            # Resource and cell keys are untrusted data, not diagnostic text.
            raise CSVError(error.reason, source_sha256=sha256(raw).hexdigest()) from None
