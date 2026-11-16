"""Native Git diff forms, bounded passive proofs, and exact failure continuation."""
import base64
from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace
import zipfile

import pytest

from apply_deletion_support import deletion_bundle, git_apply
from codex_control_tests.apply_reconcile_support import patch_package
from codex_control_tests.blocked_chain_support import log_for, git_blob
from codex_control_tests.deletion_support import result_snapshot
from codex_control_tests.test_apply_deletion_evidence import source_and_patch
from specroad_control.apply_reconcile_proof import plan, public_plan, hashed
from specroad_control.apply_snapshot import modified_files, snapshot
from specroad_control.mixed_evidence import verify_handoff
from specroad_control.job_contract import new_contract
from specroad_control.errors import ControlError


@pytest.mark.parametrize('raw',[b'',b'no newline',b'a\r\nb\n',b'\0binary\n\xff'])
@pytest.mark.parametrize('staged',[False,True])
def test_actual_git_full_index_binary_deletion_is_passively_reconstructed(tmp_path,raw,staged):
    backend=git_apply(tmp_path,raw); (backend.root/'gone.py').unlink()
    if staged: backend.git('add','-A','--','gone.py')
    patch=backend.git('diff',*(['--cached'] if staged else []),'--binary','--full-index')
    assert modified_files({'gone.py':('100644',raw),'survives.py':('100644',b'keep\n')},patch)=={
        'survives.py':('100644',b'keep\n')}


@pytest.mark.parametrize('raw',[b'',b'one\n',b'no newline',b'first\nlast'])
def test_actual_staged_new_text_file_is_reconstructed_with_its_blob_identity(tmp_path,raw):
    backend=git_apply(tmp_path);(backend.root/'new.py').write_bytes(raw);backend.git('add','--','new.py')
    patch=backend.git('diff','--cached','--binary','--full-index')
    before={'gone.py':('100644',b'original\n'),'survives.py':('100644',b'keep\n')}
    assert modified_files(before,patch)=={**before,'new.py':('100644',raw)}


def test_snapshot_rejects_divergent_index_and_worktree_even_if_final_bytes_look_safe(tmp_path):
    base={'gone.py':b'original\n'}
    fact=result_snapshot(tmp_path/'result.zip',base,{},staged=True)
    with zipfile.ZipFile(fact['path']) as z: entries={n:z.read(n) for n in z.namelist()}
    # Recreate the staged-deleted file as an unstaged addition.
    entries['changes/unstaged.patch']=(
        'diff --git a/gone.py b/gone.py\nnew file mode 100644\nindex '+'0'*40+'..'+git_blob(b'x\n')+
        '\n--- /dev/null\n+++ b/gone.py\n@@ -0,0 +1 @@\n+x\n').encode()
    with zipfile.ZipFile(fact['path'],'w') as z:
        for name,raw in entries.items(): z.writestr(name,raw)
    from pathlib import Path
    fact['sha256']=sha256(Path(fact['path']).read_bytes()).hexdigest()
    with pytest.raises(ControlError): snapshot(fact)


@pytest.mark.parametrize('fault',['missing','different','v1','clarification','parent-collision','padding'])
def test_control_rejects_the_same_ambiguous_tombstones_as_apply(tmp_path,fault):
    data=deletion_bundle();stage=data['stages'][0]
    if fault=='missing':stage.pop('delete_preimages')
    elif fault=='different':stage['delete_preimages']['gone.py']='eA=='
    elif fault=='v1': data['format_version']=1;data.pop('handoff_kind');stage.pop('role')
    elif fault=='clarification':stage['role']='clarification'
    elif fault=='parent-collision':
        stage['after']={'gone.py/child':sha256(b'x').hexdigest()};stage['payloads']={'gone.py/child':'eA=='}
    else: stage['delete_preimages']['gone.py']+='='
    package=patch_package(tmp_path/'bad.zip',data)
    with pytest.raises((ControlError,ValueError,TypeError)):plan(package)


def test_failed_source_continuation_keeps_original_bytes_and_bound_absence(tmp_path):
    source,original,data,files=source_and_patch(tmp_path)
    remaining={n:b for n,b in files.items() if n!='gone.py'}
    failed=result_snapshot(tmp_path/'failed.zip',files,remaining,
        log=log_for(data,[],failed=True),success=False,binding=data['binding'],expected=data['binding'],
        repository_path=data['apply_repository'],patch_sha256=original['sha256'],
        dry_run=False,operation='apply',entrypoint_started=True,completed_commit=None)
    correction=deepcopy(data); correction.update(source_result_sha256=failed['sha256'],initial_dirty=True,
        correction_of={'plan_sha256':hashed(public_plan(data)),'remaining_commit_ids':['step.W']})
    correction['stages'][0]['before']={}
    engine=SimpleNamespace(exchange=SimpleNamespace(candidates=lambda *a:[original]))
    package=patch_package(tmp_path/'correction.zip',correction)
    assert verify_handoff(engine,failed,package,new_contract(version=4),'patch_ready')==correction
    # An additional already-absent target is not proven by the original plan.
    correction['stages'][0]['deletions']['extra.py']=sha256(b'extra').hexdigest()
    correction['stages'][0]['delete_preimages']['extra.py']=base64.b64encode(b'extra').decode()
    package=patch_package(tmp_path/'invented.zip',correction)
    with pytest.raises(ControlError):verify_handoff(engine,failed,package,new_contract(version=4),'patch_ready')


def test_corrupt_binary_inverse_and_extra_blocks_fail_closed(tmp_path):
    backend=git_apply(tmp_path,b'\0binary\xff');(backend.root/'gone.py').unlink()
    patch=backend.git('diff','--binary','--full-index')
    files={'gone.py':('100644',b'\0binary\xff')}
    for bad in (patch.replace(b'literal 8',b'literal 9'),patch+b'literal 0\n\n'):
        with pytest.raises((ControlError,ValueError)):modified_files(files,bad)
