"""Machine-byte compatibility across distinct View and bound CSV contracts."""
import pytest

from specroad.documents import export_view
from specroad.mappings import CSVError
from support.csv_codec import column, record, selected
from support.read_only import no_write_attempts
from support.records import ref
from support.targets import model
from test_document_exports import expected_rows, read_csv, scalar_project
from test_document_exports_right import read_columns_csv
from test_document_view_variants_right import field_column


@pytest.mark.parametrize("control,json_fragment", [
    ("\x00", b"\\u0000"), ("\t", b"\\t"), ("\x1f", b"\\u001f"), ("\x7f", b"\x7f")])
@pytest.mark.parametrize("typed", [False, True])
def test_view_bytes_and_stricter_profile_character_gate_remain_distinct(control, json_fragment, typed):
    value = "a" + control + "b"
    values = scalar_project()
    for artifact in values[:-1]:
        artifact["extensions"] = {"org.example": {"value": value}}
    declaration = field_column("/extensions/org.example/value", "string")
    declaration["heading"] = "Value"
    if typed:
        declaration["serialization"] = {"csv": "typed-json-v1"}
    values[-1].update(columns=[declaration], grouping=[])
    supplied = model(values)
    before = supplied.source_files
    codec = selected([column("Value")])
    with no_write_attempts():
        raw = export_view(supplied, ref("VIEW"), output_format="csv")
        # Existing View data records: literal scalar bytes or explicit JCS tags.
        # This oracle is the machine format, never human rendering or layout.
        cell = (b'"{""type"":""string"",""value"":""a' + json_fragment + b'b""}"'
                if typed else value.encode("utf-8"))
        assert raw.startswith(b"record_type,metadata,Value\r\n")
        assert raw.split(b"\r\n", 2)[2] == (b"data,," + cell + b"\r\n") * 4
        metadata, rows = (read_columns_csv if typed else read_csv)(raw)
        assert rows == expected_rows(supplied)
        assert metadata["generated"] is True and metadata["normative"] is False
        assert metadata["notice"] == "GENERATED — DO NOT EDIT" and metadata["losses"] == []
        with pytest.raises(CSVError) as caught:
            codec.encode([record({"Value": value})])
        assert caught.value.reason == "csv_unrepresentable_character"
        assert caught.value.exit_code == 3 and caught.value.column == 2
        with pytest.raises(CSVError) as caught:
            codec.decode(("ID,Value\r\nx," + value + "\r\n").encode("utf-8"))
        assert caught.value.reason == "csv_invalid_character" and caught.value.column == 2
    assert supplied.source_files == before
