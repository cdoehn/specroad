"""14.g.R: physical framing, explicit EOF and source-bound passive resume."""
from hashlib import sha256
import json

import pytest

from specroad.exchange import (NDJSONDecoder, NDJSONError, NDJSONResumeConflict,
                              decode_ndjson, encode_ndjson, iter_decode_ndjson_chunks,
                              resume_ndjson)
from specroad.model.canonical import canonical_json_bytes
from support.domain import domain_value
from support.ndjson_codec import envelope, plan_value
from support.read_only import no_write_attempts


def rows():
    item = envelope(domain_value("requirement", statement='é 中 😀 e\u0301 // # /* */ \r\n\t \\" \ufeff',
        extensions={"example.data": {"n": -1.25e-7, "items": [None, False, 0, "", ["x", "x"]]}}))
    return [item, envelope(plan_value(), "change_plan"), item]


def wire(item):
    return json.dumps(item, ensure_ascii=False, separators=(",", ":")).encode()


def blocks(raw, size):
    for start in range(0, len(raw), size):
        yield raw[start:start + size]


def restored(source, checkpoint):
    return resume_ndjson(source, checkpoint, checkpoint_sha256=sha256(checkpoint).hexdigest())


@pytest.mark.parametrize("size", [1, 2, 3, 7, 31, 65536])
@pytest.mark.parametrize("ending", [b"", b"\n", b"\n\n"])
def test_arbitrary_blocks_keep_unicode_escapes_numbers_and_mixed_duplicates(size, ending):
    expected = rows()
    raw = b"\n\n" + b"\n\n".join(b" \t" + wire(row) + b"\t " for row in expected) + ending
    reader, actual = NDJSONDecoder(), []
    with no_write_attempts():
        for block in blocks(raw, size):
            actual.extend(reader.feed(block))
            assert reader.feed(b"") == () and not reader.observation()["complete"]
        actual.extend(reader.finish())
        assert list(iter_decode_ndjson_chunks(blocks(raw, size))) == expected
    assert actual == decode_ndjson(raw).objects == expected
    facts = reader.observation()
    assert facts["complete"] is True and facts["failed"] is False
    assert facts["source_sha256"] == sha256(raw).hexdigest()
    assert facts["object_count"] == 3 and facts["bytes_received"] == len(raw)
    assert not facts["write_authorized"] and not facts["execution_ready"]
    assert decode_ndjson(encode_ndjson(actual)).objects == expected


@pytest.mark.parametrize("raw", [b"", b"\n", b"\n\n\n"])
def test_only_explicit_eof_completes_empty_streams(raw):
    reader = NDJSONDecoder()
    assert reader.feed(raw) == reader.feed(b"") == ()
    assert not reader.observation()["complete"] and reader.observation()["source_sha256"] is None
    assert reader.finish() == () and reader.observation()["complete"]
    assert reader.observation()["source_sha256"] == sha256(raw).hexdigest()


def test_complete_object_without_lf_waits_for_real_eof_and_is_not_delivered_twice():
    expected = rows()[0]
    reader = NDJSONDecoder()
    assert reader.feed(wire(expected)) == ()
    for _ in range(3):
        assert reader.feed(b"") == () and reader.observation()["object_count"] == 0
    assert reader.finish() == (expected,)
    for action in (lambda: reader.feed(b"\n"), reader.finish, lambda: reader.checkpoint(wire(expected))):
        with pytest.raises(NDJSONError): action()


BAD_LINES = [
    b" ", b"\t", b" \t ", b"// private-comment", b"# private-comment", b"/* private-comment */",
    b'{"a":1,}', b'{"a":[1,]}', b'{"a":{"b":1,"b":2}}', b'{"a":1,"\\u0061":2}',
    b"{} {}", b"[]", b"1", b"null", b"true", b'"private-value"',
    b"\xef\xbb\xbf{}", b"\r", b"{}\r", b"\xff", b"\xc0\xaf", b"\xed\xa0\x80",
    b'{"a":NaN}', b'{"a":Infinity}', b'{"a":1e9999}', b'{"a":9007199254740993}',
    b'{"a":"\\ud800"}', b'{"a":"\x00"}', b'{"a":"unfinished', b'{"a":"\xf0\x9f',
    b'{"a":', b'{', b'{"a":"escape\\',
]


@pytest.mark.parametrize("bad", BAD_LINES)
@pytest.mark.parametrize("terminated", [False, True])
def test_bad_physical_lines_fail_after_blank_lines_without_leaking_values(bad, terminated):
    prefix = b"\n" + wire(rows()[0]) + b"\n\n"
    raw = prefix + bad + (b"\n" if terminated else b"")
    reader = NDJSONDecoder()
    assert reader.feed(prefix) == (rows()[0],)
    with pytest.raises(NDJSONError) as caught:
        for block in blocks(raw[len(prefix):], 1): reader.feed(block)
        reader.finish()
    assert caught.value.line == 4 and caught.value.exit_code == 3
    assert "private-" not in json.dumps(caught.value.diagnostic())
    assert not reader.observation()["complete"] and reader.observation()["failed"]
    for action in (lambda: reader.feed(wire(rows()[0]) + b"\n"), reader.finish,
                   lambda: reader.checkpoint(raw)):
        with pytest.raises(NDJSONError): action()
    with pytest.raises(NDJSONError) as whole: decode_ndjson(raw)
    assert whole.value.line == caught.value.line and whole.value.reason == caught.value.reason


@pytest.mark.parametrize("defect", ["native", "duplicate", "plan-hash", "multiline", "raw-cr"])
def test_error_pointers_and_physical_lines_are_independent_of_chunk_boundaries(defect):
    item = rows()[0]
    expected_pointer = ""
    if defect == "native":
        item["object"]["revision"] = "private-invalid-revision"
        bad, expected_pointer = wire(item), "/object/revision"
    elif defect == "duplicate":
        item["object"]["extensions"] = {"example.data": {"a/b~c": 0}}
        bad = wire(item).replace(b'"a/b~c":0', b'"a/b~c":0,"a/b~c":1')
        expected_pointer = "/object/extensions/example.data/a~1b~0c"
    elif defect == "plan-hash":
        item = rows()[1]
        item["object"]["change_plan_sha256"] = "0" * 64
        bad, expected_pointer = wire(item), "/object/change_plan_sha256"
    elif defect == "multiline":
        bad = wire(item).replace(b',"object_kind"', b',\n"object_kind"')
    else:
        bad = wire(item).replace(b"//", b"\r//")
    raw = b"\n\n" + bad + b"\n"
    with pytest.raises(NDJSONError) as caught:
        list(iter_decode_ndjson_chunks(blocks(raw, 3)))
    assert caught.value.line == 3 and caught.value.pointer == expected_pointer
    assert "private-invalid-revision" not in json.dumps(caught.value.diagnostic())


def test_pauses_inside_utf8_escape_number_and_plan_do_not_mean_eof():
    raw = b"\n" + b"\n".join(wire(row) for row in rows())
    cuts = {0, 1, len(raw) - 1, len(raw)}
    for needle in ('😀'.encode(), b'\\r', b'1.25e-07', b'"change_plan_sha256"'):
        at = raw.index(needle)
        cuts.update(range(at, at + len(needle) + 1))
    for cut in sorted(cuts):
        reader = NDJSONDecoder()
        confirmed = list(reader.feed(raw[:cut]))
        assert reader.feed(b"") == () and not reader.observation()["complete"]
        checkpoint = reader.checkpoint(raw)
        following = restored(raw, checkpoint)
        assert following.observation() == reader.observation()
        actual = confirmed + list(following.feed(raw[cut:])) + list(following.finish())
        assert actual == rows() and following.observation()["source_sha256"] == sha256(raw).hexdigest()


def test_multiple_persisted_cursors_continue_exactly_once_at_blank_and_record_boundaries(tmp_path):
    expected = rows()
    raw = b"\n\n" + b"\n\n".join(wire(row) for row in expected) + b"\n\n"
    # Host persistence is explicit. The codec itself does not open these paths.
    source_path, saved_path = tmp_path / "source", tmp_path / "cursor"
    source_path.write_bytes(raw)
    reader, actual, previous = NDJSONDecoder(), [], 0
    cuts = [1, 2, raw.index(b"\n", 2) + 1, len(raw) - 2, len(raw)]
    for cut in cuts:
        actual.extend(reader.feed(raw[previous:cut]))
        checkpoint = reader.checkpoint(raw)
        trusted_hash = sha256(checkpoint).hexdigest()
        saved_path.write_bytes(checkpoint)
        reader = resume_ndjson(source_path.read_bytes(), saved_path.read_bytes(), checkpoint_sha256=trusted_hash)
        previous = cut
    actual.extend(reader.finish())
    assert actual == expected and reader.observation()["object_count"] == 3


@pytest.mark.parametrize("change", ["consumed", "pending", "unread", "shorter", "longer"])
def test_changed_source_is_a_conflict_before_resumed_output(change):
    raw = encode_ndjson(rows())
    cut = raw.index(b"\n") + 9
    reader = NDJSONDecoder(); reader.feed(raw[:cut])
    checkpoint = reader.checkpoint(raw)
    if change == "shorter": changed = raw[:-1]
    elif change == "longer": changed = raw + b"\n"
    else:
        at = {"consumed": 4, "pending": cut - 1, "unread": len(raw) - 2}[change]
        changed = raw[:at] + bytes([raw[at] ^ 1]) + raw[at + 1:]
    with pytest.raises(NDJSONResumeConflict) as caught: restored(changed, checkpoint)
    assert caught.value.exit_code == caught.value.diagnostic()["exit_code"] == 6


@pytest.mark.parametrize("change", ["bytes", "digest", "other-cursor"])
def test_saved_checkpoint_must_match_independently_retained_hash(change):
    raw = encode_ndjson(rows())
    reader = NDJSONDecoder(); reader.feed(raw[:2])
    checkpoint = reader.checkpoint(raw)
    trusted = sha256(checkpoint).hexdigest()
    if change == "bytes": checkpoint += b" "
    elif change == "digest": trusted = "0" * 64
    else:
        reader.feed(raw[2:4]); checkpoint = reader.checkpoint(raw)
    with pytest.raises(NDJSONResumeConflict) as caught:
        resume_ndjson(raw, checkpoint, checkpoint_sha256=trusted)
    assert caught.value.reason == "ndjson_checkpoint_changed" and caught.value.exit_code == 6


@pytest.mark.parametrize("field,value", [
    ("format_version", "unknown"), ("byte_offset", True), ("byte_offset", -1),
    ("byte_offset", 999999), ("byte_offset", 0), ("next_line", 0), ("next_line", 99),
    ("object_count", 99), ("object_count", False), ("pending_hex", "00"),
    ("pending_hex", []), ("source_sha256", None), ("source_sha256", "G" * 64), ("extra", None),
])
def test_cursor_geometry_and_closed_contract_are_revalidated(field, value):
    raw = encode_ndjson(rows())
    reader = NDJSONDecoder(); reader.feed(raw[:raw.index(b"\n") + 3])
    data = json.loads(reader.checkpoint(raw)); data[field] = value
    checkpoint = canonical_json_bytes(data)
    with pytest.raises(NDJSONError) as caught: restored(raw, checkpoint)
    assert caught.value.reason == "ndjson_invalid_checkpoint" and caught.value.exit_code == 3


@pytest.mark.parametrize("checkpoint", [b"", b"[]", b"{}", b'{"x":1,"x":2}', b"\xff"])
def test_malformed_checkpoint_is_never_treated_as_an_empty_reader(checkpoint):
    with pytest.raises(NDJSONError) as caught: restored(b"", checkpoint)
    assert caught.value.reason == "ndjson_invalid_checkpoint"


def test_even_self_consistent_forged_cursor_cannot_skip_an_invalid_prefix():
    raw = b"{bad}\n" + encode_ndjson(rows())
    checkpoint = canonical_json_bytes({"format_version": "ndjson-cursor-v1",
        "source_sha256": sha256(raw).hexdigest(), "source_size": len(raw), "byte_offset": 6,
        "next_line": 2, "object_count": 1, "pending_hex": ""})
    with pytest.raises(NDJSONError) as caught: restored(raw, checkpoint)
    assert caught.value.line == 1 and caught.value.reason == "invalid_json"


@pytest.mark.parametrize("change", ["different", "early-eof", "overflow"])
def test_live_reader_cannot_change_bound_remaining_source_or_finish_early(change):
    raw = encode_ndjson(rows())
    reader = NDJSONDecoder(); reader.feed(raw[:2]); checkpoint = reader.checkpoint(raw)
    reader = restored(raw, checkpoint)
    with pytest.raises(NDJSONResumeConflict):
        if change == "different": reader.feed(b"wrong")
        elif change == "early-eof": reader.finish()
        else: reader.feed(raw[2:] + b"\n")
    assert not reader.observation()["complete"] and reader.observation()["failed"]


def test_checkpoint_source_must_include_exact_consumed_prefix_and_cannot_be_rebound():
    raw = encode_ndjson(rows())
    reader = NDJSONDecoder(); reader.feed(raw[:2])
    for source in (raw[:1], b"xx" + raw[2:]):
        with pytest.raises(NDJSONResumeConflict): reader.checkpoint(source)
    reader.checkpoint(raw)
    with pytest.raises(NDJSONResumeConflict): reader.checkpoint(raw + b"\n")
    assert list(reader.feed(raw[2:])) + list(reader.finish()) == rows()


@pytest.mark.parametrize("bad", [None, "", bytearray(b"{}"), [], 1])
def test_mutable_or_nonbyte_transfer_blocks_cannot_be_silently_accepted(bad):
    reader = NDJSONDecoder()
    with pytest.raises(NDJSONError): reader.feed(bad)
    assert reader.observation()["failed"] and not reader.observation()["complete"]


def test_large_line_and_many_duplicate_records_have_no_total_size_or_count_cutoff():
    item = envelope(domain_value(statement="é" * 200000))
    raw = wire(item) + b"\n"
    reader = NDJSONDecoder()
    split = len(raw) - 11
    for block in blocks(raw[:split], 17): assert reader.feed(block) == ()
    reader = restored(raw, reader.checkpoint(raw))
    assert reader.feed(raw[split:]) == (item,) and reader.finish() == ()
    small_item = rows()[0]
    small = wire(small_item) + b"\n"
    reader = NDJSONDecoder()
    for _ in range(2000): assert reader.feed(small) == (small_item,)
    assert reader.finish() == () and reader.observation()["object_count"] == 2000


def test_block_iterator_does_not_turn_a_producer_failure_into_eof():
    first = rows()[0]
    failure = OSError("host failure")
    def producer():
        yield wire(first) + b"\n"
        raise failure
    result = iter_decode_ndjson_chunks(producer())
    assert next(result) == first
    with pytest.raises(OSError) as caught: next(result)
    assert caught.value is failure


@pytest.mark.parametrize("failure", [MemoryError(), OSError(), PermissionError()])
def test_resource_and_security_errors_keep_their_classes_and_poison_partial_reader(monkeypatch, failure):
    import specroad.exchange.ndjson as codec
    def fail(*args, **kwargs): raise failure
    reader = NDJSONDecoder()
    monkeypatch.setattr(codec, "_validate_envelope", fail)
    with pytest.raises(type(failure)) as caught: reader.feed(wire(rows()[0]) + b"\n")
    assert caught.value is failure and reader.observation()["failed"]
    with pytest.raises(NDJSONError): reader.finish()


def test_resume_and_chunk_decoding_do_not_open_files_or_execute_plans(monkeypatch):
    import builtins
    import io
    import os
    import specroad.changes as changes
    import specroad.changes.execution as execution
    import specroad.work.checkpoints as checkpoints
    raw, expected = encode_ndjson(rows()), rows()
    def forbidden(*args, **kwargs): raise AssertionError("Unexpected host action")
    with no_write_attempts(), monkeypatch.context() as patcher:
        for owner, name in ((builtins, "open"), (io, "open"), (os, "open"),
                            (changes, "apply_change_plan"), (execution, "apply_change_plan"),
                            (checkpoints.CheckpointStore, "publish")):
            patcher.setattr(owner, name, forbidden)
        reader = NDJSONDecoder(); confirmed = list(reader.feed(raw[:73]))
        reader = restored(raw, reader.checkpoint(raw))
        assert confirmed + list(reader.feed(raw[73:])) + list(reader.finish()) == expected
        assert not reader.observation()["write_authorized"]


@pytest.mark.parametrize("mode", ["core", "pyz"])
def test_incremental_resume_is_available_in_isolated_core_and_pyz(mode, tmp_path):
    from support.portable import build_distribution
    from support.processes import run_core, run_python
    raw = encode_ndjson(rows())
    body = "\n".join([
        "from hashlib import sha256",
        "from specroad.exchange import NDJSONDecoder, resume_ndjson",
        "raw=" + repr(raw), "reader=NDJSONDecoder()", "prior=reader.feed(raw[:17])",
        "saved=reader.checkpoint(raw)",
        "reader=resume_ndjson(raw,saved,checkpoint_sha256=sha256(saved).hexdigest())",
        "assert len(prior+reader.feed(raw[17:])+reader.finish())==3",
        "assert reader.observation()['complete'] and not reader.observation()['write_authorized']"])
    if mode == "core": result = run_core(body, tmp_path)
    else:
        _, app = build_distribution(tmp_path / "dist")
        result = run_python(["-I", "-S", "-B", "-c", "import sys;sys.path.insert(0," + repr(str(app)) + ");" + body], tmp_path)
    assert result.returncode == 0, result.stderr
