"""SR-FIX-CSV-CODEC-v1: explicit profiles, mappings and passive records."""
from specroad.exchange import select_csv_profile
from specroad.mappings import CSVProfile, ExchangeMapping
from support.artifacts import artifact_bytes
from support.exchange_mappings import mapping_value


def column(name, kind="string", *, empty="value", missing="error"):
    codec = {"kind": kind}
    if kind == "list":
        codec["list_rule"] = "json-array-v1"
    return {"column": name, "external_field": name, "codec": codec,
            "empty_cell": "error" if kind == "typed-json-v1" else empty,
            "missing_column": missing}


def resources(columns=None, *, identity_column="ID", identity_kind="external_id"):
    if columns is None:
        columns = [column("Text"), column("Flag", "boolean"), column("Count", "integer"),
                   column("Measure", "number"), column("Items", "list"),
                   column("State", "typed-json-v1")]
    mapping = ExchangeMapping(artifact_bytes(mapping_value(source_format="csv", fields=[
        {"external_type": "Requirement", "external_field": c["external_field"],
         "target_field": "value-" + str(i), "value_map": None} for i, c in enumerate(columns)])))
    value = {"schema_version": "0.2.0", "mapping_format_version": "csv-profile-v1",
        "mapping_id": "example:csv", "mapping_version": "1.0.0", "mapping": mapping.binding(),
        "external_type": "Requirement", "identity": {"column": identity_column, "kind": identity_kind},
        "columns": columns, "error_policy": "reject", "extensions": {"example.passive": "=1+1"}}
    return CSVProfile(artifact_bytes(value)), mapping


def selected(columns=None, **kwargs):
    profile, mapping = resources(columns, **kwargs)
    return select_csv_profile([profile, mapping], key=profile.key, expected_sha256=profile.sha256)


def record(fields, *, identity="external-1", kind="external_id"):
    return {"identity": {"kind": kind, "value": identity}, "external_type": "Requirement", "fields": fields}
