"""17.d.W: byte-preserving attachment candidates and explicit removal intent."""
from dataclasses import FrozenInstanceError
from hashlib import sha256

import pytest

from specroad.merge import merge_attachments
from specroad.model.errors import ModelError

PATH = 'attachments/data.bin'


@pytest.mark.parametrize('base,ours,theirs,expected', [
    (b'old', b'old', b'old', b'old'),
    (b'old', b'new', b'old', b'new'),
    (b'old', b'old', b'new', b'new'),
    (b'old', b'new', b'new', b'new'),
    (b'old', b'', b'', b''),
    (None, b'new', None, b'new'),
    (None, None, b'new', b'new'),
    (None, b'\x00\xff', b'\x00\xff', b'\x00\xff'),
])
def test_three_way_binary_matrix_preserves_exact_bytes(base, ours, theirs, expected):
    values = [{} if value is None else {PATH:value} for value in (base, ours, theirs)]
    before = [dict(value) for value in values]
    result = merge_attachments(*values)
    assert result.merged and result.files == {PATH:expected} and result.conflicts == ()
    assert values == before
    assert result.ready is False and result.write_authorized is False


def test_independent_paths_keep_both_even_with_identical_payload_hashes():
    result = merge_attachments({}, {'attachments/a':b'same'}, {'attachments/b':b'same'})
    assert result.files == {'attachments/a':b'same', 'attachments/b':b'same'}


@pytest.mark.parametrize('base', [None, b'base'])
def test_different_bytes_at_one_path_are_conflicts_with_real_hashes(base):
    result = merge_attachments({} if base is None else {PATH:base}, {PATH:b'ours'}, {PATH:b'theirs'})
    conflict, = result.conflicts
    assert conflict.path == PATH and conflict.kind == 'attachment_binary_change'
    assert (conflict.base_sha256, conflict.ours_sha256, conflict.theirs_sha256) == tuple(
        None if value is None else sha256(value).hexdigest() for value in (base, b'ours', b'theirs'))
    with pytest.raises(ModelError) as caught:
        _ = result.files
    assert caught.value.reason == 'unresolved_attachment_merge'


@pytest.mark.parametrize('ours,theirs', [(None,b'base'),(b'base',None),(None,None),(None,b'edited')])
def test_absence_never_invents_removal_intent(ours, theirs):
    result = merge_attachments({PATH:b'base'}, {} if ours is None else {PATH:ours}, {} if theirs is None else {PATH:theirs})
    conflict, = result.conflicts
    assert conflict.kind == 'attachment_absence_unproven'
    assert conflict.base_sha256 == sha256(b'base').hexdigest()
    assert (conflict.ours_sha256 is None) is (ours is None)
    assert (conflict.theirs_sha256 is None) is (theirs is None)


@pytest.mark.parametrize('side', ['ours','theirs','both'])
def test_explicit_removal_against_unchanged_or_same_removal_is_only_a_candidate(side):
    base = {PATH:b'base'}; ours, theirs = dict(base), dict(base); wishes = {}
    if side in ('ours','both'):
        ours.clear(); wishes['removed_ours'] = [PATH]
    if side in ('theirs','both'):
        theirs.clear(); wishes['removed_theirs'] = [PATH]
    result = merge_attachments(base, ours, theirs, **wishes)
    assert result.files == {} and result.merged
    assert result.ready is False and result.write_authorized is False


@pytest.mark.parametrize('side', ['ours','theirs'])
def test_explicit_remove_edit_is_a_conflict(side):
    values = [{PATH:b'base'}, {}, {PATH:b'edited'}]
    if side == 'theirs':
        values[1], values[2] = values[2], values[1]
    result = merge_attachments(*values, **{'removed_'+side:[PATH]})
    assert result.conflicts[0].kind == 'attachment_remove_edit'


@pytest.mark.parametrize('removals', [[PATH,PATH], ['attachments/unknown'], PATH, None, [True]])
def test_invalid_removal_wishes_are_rejected(removals):
    with pytest.raises(ModelError) as caught:
        merge_attachments({PATH:b'base'}, {}, {PATH:b'base'}, removed_ours=removals)
    assert caught.value.reason == 'invalid_attachment_removal'


def test_removal_cannot_name_a_still_present_file():
    with pytest.raises(ModelError) as caught:
        merge_attachments({PATH:b'base'}, {PATH:b'base'}, {}, removed_ours=[PATH])
    assert caught.value.reason == 'invalid_attachment_removal'


@pytest.mark.parametrize('path', ['outside.bin','attachments/../escape','/attachments/a','attachments/a//b',
    'attachments/a\\b','attachments/.git/config','attachments/CON','attachments/a.'])
def test_attachment_paths_are_checked_without_reading_them(path):
    with pytest.raises(ModelError):
        merge_attachments({}, {path:b'bytes'}, {})


@pytest.mark.parametrize('value', ['data', bytearray(b'data'), memoryview(b'data'), None, {'sha256':'0'*64}])
def test_only_actual_immutable_bytes_are_accepted(value):
    with pytest.raises(ModelError) as caught:
        merge_attachments({}, {PATH:value}, {})
    assert caught.value.reason == 'invalid_merge_attachment_bytes'


def test_binary_results_are_detached_immutable_and_never_truthy_authority():
    values = [{}, {PATH:b'bytes'}, {}]
    result = merge_attachments(*values); values[1].clear(); detached = result.files; detached.clear()
    assert result.files == {PATH:b'bytes'}
    with pytest.raises(TypeError):
        bool(result)
    with pytest.raises(FrozenInstanceError):
        result.conflicts = ()
