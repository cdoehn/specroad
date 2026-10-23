"""Bound, pure CSV dataset codec. No native projection or import authority."""
from dataclasses import dataclass
from hashlib import sha256

from ..mappings.csv_profile import CSVError, CSVProfile
from ..mappings._resources import ExchangeMapping, ExternalIdentityRegistry, _select
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..model.paths import artifact_path
from ..storage.json_syntax import parse_json_object
from ._csv_cells import MISSING, decode_cell, encode_cell
from ._csv_syntax import read_rows, write_row


@dataclass(frozen=True)
class CSVObservation:
    """Complete input observation; detached records never authorize a write."""
    source_bytes: bytes
    _records: bytes
    _bindings: bytes

    @property
    def records(self):
        return parse_json_object(self._records)["records"]

    def observation(self):
        return {**parse_json_object(self._bindings),
                "source_sha256": sha256(self.source_bytes).hexdigest(),
                "record_count": len(self.records)}


@dataclass(frozen=True)
class _SelectedCSVProfile:
    """Exact supplied profile/mapping bytes, selected by explicit key and hash."""
    _profile_bytes: bytes
    _mapping_bytes: bytes

    @property
    def profile(self):
        return CSVProfile(self._profile_bytes)

    @property
    def mapping(self):
        return ExchangeMapping(self._mapping_bytes)

    def _context(self):
        profile, mapping = self.profile, self.mapping
        p, m = profile.data, mapping.data
        if p["mapping"] != mapping.binding() or profile.key == mapping.key:
            raise CSVError("csv_mapping_binding", profile=profile.binding(), mapping=mapping.binding())
        types = {row["external_type"]: row["artifact_type"] for row in m["types"]}
        fields = {row["external_field"] for row in m["fields"] if row["external_type"] == p["external_type"]}
        if (m["source_format"] != "csv" or p["external_type"] not in types
                or fields != {row["external_field"] for row in p["columns"]}):
            raise CSVError("csv_mapping_contract", profile=profile.binding(), mapping=mapping.binding())
        return p, types[p["external_type"]], {
            "profile": {**profile.binding(), "source_sha256": profile.source_sha256},
            "mapping": {**mapping.binding(), "source_sha256": mapping.source_sha256}}

    def decode(self, raw):
        p, artifact_type, bindings = self._context()
        source_hash = sha256(raw).hexdigest() if type(raw) is bytes else None
        record, column = None, None
        try:
            rows = iter(read_rows(raw))
            header = next(rows)
            record = 1
            declared = {row["column"] for row in p["columns"]} | {p["identity"]["column"]}
            if any(not name for name in header) or len(header) != len(set(header)) or set(header) - declared:
                raise CSVError("csv_invalid_header")
            positions = {name: i for i, name in enumerate(header)}
            if p["identity"]["column"] not in positions:
                raise CSVError("csv_identity_header_required")
            for rule in p["columns"]:
                if rule["column"] not in positions and rule["missing_column"] == "error":
                    raise CSVError("csv_column_required")
            records, identities = [], set()
            for record, cells in enumerate(rows, 2):
                column = None
                if len(cells) != len(header):
                    raise CSVError("csv_row_width")
                column = positions[p["identity"]["column"]] + 1
                identity = cells[column - 1]
                _identity(identity, p["identity"]["kind"], artifact_type, identities)
                fields = {}
                for rule in p["columns"]:
                    if rule["column"] not in positions:
                        continue
                    column = positions[rule["column"]] + 1
                    value = decode_cell(cells[column - 1], rule)
                    if value is not MISSING:
                        fields[rule["external_field"]] = value
                records.append({"identity": {"kind": p["identity"]["kind"], "value": identity},
                                "external_type": p["external_type"], "fields": fields})
            return CSVObservation(raw, canonical_json_bytes({"records": records}), canonical_json_bytes(bindings))
        except ModelError as error:
            raise CSVError(error.reason, **bindings, source_sha256=source_hash,
                           record=getattr(error, "record", None) or record,
                           column=(error.column or column) if isinstance(error, CSVError) else column) from None

    def encode(self, records):
        p, artifact_type, bindings = self._context()
        record, column = 1, None
        try:
            if type(records) not in (list, tuple):
                raise CSVError("csv_record_sequence_required")
            identity_column = p["identity"]["column"]
            header = [identity_column] + [r["column"] for r in p["columns"] if r["column"] != identity_column]
            output, identities = [write_row(header, header=True)], set()
            allowed = {r["external_field"] for r in p["columns"]}
            for record, item in enumerate(records, 2):
                column = None
                if type(item) is not dict or set(item) != {"identity", "external_type", "fields"}:
                    raise CSVError("csv_record_required")
                identity, fields = item["identity"], item["fields"]
                if (type(identity) is not dict or set(identity) != {"kind", "value"}
                        or identity["kind"] != p["identity"]["kind"]
                        or item["external_type"] != p["external_type"]):
                    raise CSVError("csv_record_binding")
                column = 1
                _identity(identity["value"], identity["kind"], artifact_type, identities)
                if type(fields) is not dict or any(type(k) is not str for k in fields) or set(fields) - allowed:
                    raise CSVError("csv_unknown_fields")
                cells = {identity_column: identity["value"]}
                positions = {name: i + 1 for i, name in enumerate(header)}
                for rule in p["columns"]:
                    column = positions[rule["column"]]
                    text = encode_cell(fields.get(rule["external_field"], MISSING), rule)
                    if rule["column"] == identity_column and text != identity["value"]:
                        raise CSVError("csv_identity_field_mismatch")
                    cells[rule["column"]] = text
                output.append(write_row([cells[name] for name in header]))
            return b"".join(output)
        except ModelError as error:
            raise CSVError(error.reason, **bindings, record=record, column=error.column or column) from None


def _identity(value, kind, artifact_type, seen):
    if type(value) is not str or not value:
        raise CSVError("csv_identity_required")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise CSVError("csv_invalid_identity") from None
    if kind == "native_id":
        artifact_path(artifact_type, value, value.split("-", 1)[0])
    if value in seen:
        raise CSVError("csv_duplicate_identity")
    seen.add(value)


def select_csv_profile(resources, *, key, expected_sha256):
    """Select supplied resources only; registry keys participate in collisions."""
    profile, mapping = None, None
    try:
        if type(resources) not in (list, tuple):
            raise CSVError("csv_resources_required")
        indexed = {}
        for resource in resources:
            if type(resource) not in (CSVProfile, ExchangeMapping, ExternalIdentityRegistry):
                raise CSVError("csv_resource_type")
            owned = type(resource)(resource.source_bytes)
            if owned.key in indexed:
                raise CSVError("csv_duplicate_resource", source_sha256=owned.source_sha256)
            indexed[owned.key] = owned
        profile = indexed.get(key) if type(key) is str else None
        profile = _select(indexed, key, expected_sha256)
        if type(profile) is not CSVProfile:
            raise CSVError("csv_profile_required")
        bound = profile.data["mapping"]
        mapping_key = bound["mapping_id"] + "@" + bound["mapping_version"]
        mapping = indexed.get(mapping_key)
        mapping = _select(indexed, mapping_key, bound["sha256"])
        if type(mapping) is not ExchangeMapping:
            raise CSVError("csv_exchange_mapping_required")
        codec = _SelectedCSVProfile(profile.source_bytes, mapping.source_bytes)
        codec._context()
        return codec
    except ModelError as error:
        raise CSVError(error.reason,
                       profile=profile.binding() if profile is not None else None,
                       mapping=mapping.binding() if mapping is not None else None,
                       source_sha256=getattr(error, "source_sha256", None)) from None
