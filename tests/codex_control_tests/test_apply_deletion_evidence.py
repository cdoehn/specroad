"""Control proves deletion state passively from exact plans and native snapshots."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from apply_deletion_support import deletion_bundle
from codex_control_tests.apply_reconcile_support import patch_package
from codex_control_tests.blocked_chain_support import log_for
from codex_control_tests.deletion_support import deletion_diff, result_snapshot
from specroad_control.apply_reconcile_proof import (plan, public_plan, canonical,
    DELETION_CAPABILITY_PATH, DELETION_CAPABILITY)
from specroad_control.apply_snapshot import snapshot, apply_stage, modified_files
from specroad_control.mixed_evidence import verify_handoff, verify_followup
from specroad_control.job_contract import new_contract
from specroad_control.errors import ControlError
from verification_support.bundle_contract import public_plan as apply_public


@pytest.mark.parametrize('raw', [b'', b'old\n', b'no newline', b'\0binary'])
@pytest.mark.parametrize('staged', [False, True])
def test_native_snapshot_reconstructs_deleted_bytes_without_patch_execution(tmp_path, raw, staged):
    base = {'gone.py':raw,'keep.py':b'keep\n'}
    source = result_snapshot(tmp_path/'result.zip',base,{'keep.py':b'keep\n'},staged=staged)
    before, work = snapshot(source)
    assert before['gone.py'] == ('100644',raw)
    assert work == {'keep.py':('100644',b'keep\n')}


def test_control_and_apply_agree_on_full_plan_and_public_deletion_identity(tmp_path):
    data = deletion_bundle()
    package = patch_package(tmp_path/'patch.zip', data)
    decoded, _ = plan(package)
    assert decoded == data
    assert public_plan(decoded) == apply_public(data)
    assert apply_stage({'gone.py':('100644',b'original\n')}, decoded['stages'][0]) == {}


def source_and_patch(tmp_path, *, installed=True):
    data = deletion_bundle()
    files = {'gone.py':b'original\n','tests/test_surviving.py':b'def test_alive(): pass\n'}
    if installed:
        files[DELETION_CAPABILITY_PATH] = canonical(DELETION_CAPABILITY) + b'\n'
    source = result_snapshot(tmp_path/'source.zip',files,files,binding=data['binding'],
                             repository_path=data['apply_repository'])
    data['source_result_sha256'] = source['sha256']
    package = patch_package(tmp_path/'patch.zip',data)
    return source, package, data, files


def test_handoff_requires_deletion_support_in_committed_native_source(tmp_path):
    source, package, data, _ = source_and_patch(tmp_path)
    assert verify_handoff(None,source,package,new_contract(version=4),'patch_ready') == data
    source, package, _, _ = source_and_patch(tmp_path,installed=False)
    with pytest.raises(ControlError):
        verify_handoff(None,source,package,new_contract(version=4),'patch_ready')


@pytest.mark.parametrize('success', [False, True])
def test_followup_accepts_proven_deletion_with_failed_or_completed_gate(tmp_path, success):
    source, package, data, files = source_and_patch(tmp_path)
    work = {n:b for n,b in files.items() if n != 'gone.py'}
    head = 'c'*40 if success else data['binding']['base_commit']
    result = result_snapshot(tmp_path/'result.zip',work if success else files,work,
        log=log_for(data,['c'*40] if success else [],failed=not success), success=success,
        binding={**data['binding'],'base_commit':head},expected=data['binding'],patch_sha256=package['sha256'],
        dry_run=False,operation='apply',entrypoint_started=True,repository_path=data['apply_repository'],
        completed_commit=head if success else None)
    engine = SimpleNamespace(exchange=SimpleNamespace(patches=lambda _: [package]))
    assert verify_followup(engine,source,package['sha256'],result,'patch_ready') == {
        'verified':True,'pending_clarification':False}


def test_reappeared_or_unbound_deleted_bytes_are_not_a_valid_stage(tmp_path):
    stage = deletion_bundle()['stages'][0]
    with pytest.raises(ControlError): apply_stage({'gone.py':('100644',b'foreign\n')},stage)
    missing = deepcopy(stage); missing['before'] = {}
    with pytest.raises(ControlError): apply_stage({'gone.py':('100644',b'original\n')},missing)
    missing['delete_preimages']['gone.py'] = 'Zm9yZWlnbg=='
    with pytest.raises(ControlError): apply_stage({},missing)


def test_deleted_diff_must_account_for_every_byte_and_original_blob():
    files = {'gone.py':('100644',b'one\ntwo\n')}
    diff = deletion_diff('gone.py',b'one\ntwo\n')
    for changed in (diff.replace(b'-two\n',b'-other\n'), diff.replace(b'+0,0',b'+1,0'), diff+diff):
        with pytest.raises(ControlError): modified_files(files,changed)
