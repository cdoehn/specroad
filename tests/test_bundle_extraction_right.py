"""15.e.R: real interrupted roots, exact replay input and preserved foreign data."""
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from specroad.authoring import _bootstrap_io as io
from specroad.bundles import prepare_partial_bundle
from specroad.bundles import extraction
from specroad.bundles._extraction_record import COMPLETED
from specroad.changes._lock_files import LockFiles
from specroad.cli.application import dispatch_result
from specroad.model.canonical import canonical_json_bytes
from specroad.security import SafetyViolation
from specroad.storage.project import ProjectSource
from support.command_parity import process_environment, run_python
from support.read_only import inventory, no_write_attempts
from test_bundle_extraction import check_files
from test_bundle_verification import bundle
from test_bundle_verification_right import reviewed
from test_partial_bundle import scope
from test_product_bundle_right import CORPUS
from test_project_initialization_right import no_bootstrap_writes, preserved


CRASH_BODY = '''
import os, sys
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from specroad.authoring import _bootstrap_io as io
from specroad.bundles.extraction import extract_bundle
source, target, cut, expected = sys.argv[2:]
prepare, move, native, finish = io.BootstrapTree.prepare, io.rename_new, io._rename_native, io.BootstrapTree.retain_completed
def prepared(self, *args, **kwargs):
    prepare(self, *args, **kwargs)
    if cut == 'prepared': os._exit(73)
def moved(function, source_fd, source, target_fd, destination):
    move(function, source_fd, source, target_fd, destination)
    if cut == destination: os._exit(73)
def native_moved(function, source_fd, source, target_fd, destination):
    native(function, source_fd, source, target_fd, destination)
    if cut == 'receipt-move' and source == io.STAGING: os._exit(73)
def finished(self):
    finish(self)
    if cut == 'complete': os._exit(73)
io.BootstrapTree.prepare, io.rename_new = prepared, moved
io._rename_native, io.BootstrapTree.retain_completed = native_moved, finished
extract_bundle(Path(source).read_bytes(), target, expected_sha256=expected)
raise AssertionError('fault boundary was not reached')
'''


def inputs(tmp_path, kind='project'):
    root = tmp_path / 'origin'
    if kind == 'project': original = bundle(root)
    else:
        reviewed(root, kind)
        original = prepare_partial_bundle(root, scope(kind))
    source = tmp_path / 'input.zip'; source.write_bytes(original.source_bytes)
    return original, source, tmp_path / 'output'


def invoke(source, target, expected=None):
    argv = ['bundle', 'extract', str(source), '--output', str(target)]
    if expected is not None: argv += ['--expected-sha256', expected]
    return dispatch_result(argv)


def interrupt(source, target, cut='prepared'):
    repository = Path(__file__).resolve().parents[1]
    result = run_python(CRASH_BODY,
        [str(repository/'src'), str(source), str(target), cut, sha256(source.read_bytes()).hexdigest()],
        cwd=target.parent, environment=process_environment())
    assert result.returncode == 73, (result.stdout, result.stderr)
    stage = target / io.STAGING
    receipt = target.joinpath(*COMPLETED)
    record = (stage if stage.exists() else receipt) / 'journal.json'
    return record, json.loads(record.read_bytes())


PROJECT_UNITS = ['.specroad', 'attachments', 'bundle-manifest.json', 'mappings',
                 'profiles', 'spec', 'specroad.json']






















@pytest.mark.parametrize('where',['root','parent'])
def test_replaced_target_ancestry_cannot_redirect_publication(tmp_path,monkeypatch,where):
    original,source,_=inputs(tmp_path)
    parent=tmp_path/'parent';parent.mkdir();target=parent/'output';moved=tmp_path/'displaced'
    native=io.BootstrapTree.prepare
    def replace(tree,*args,**kwargs):
        native(tree,*args,**kwargs)
        old=target if where=='root' else parent
        old.rename(moved);old.mkdir();(old/'foreign').write_bytes(b'preserve replacement')
    monkeypatch.setattr(io.BootstrapTree,'prepare',replace)
    result=invoke(source,target)
    # Replaced descriptor ancestry is the native security contract, not a model conflict.
    assert result.exit_code==7 and result.as_dict()['result'] is None
    replacement=target if where=='root' else parent
    assert (replacement/'foreign').read_bytes()==b'preserve replacement'
    assert set(p.name for p in replacement.iterdir())=={'foreign'}
    displaced=moved if where=='root' else moved/'output'
    assert (displaced/io.STAGING/'journal.json').exists()




@pytest.mark.parametrize('locked',['parent','target'])
def test_real_native_mutex_prevents_competing_extraction(tmp_path,locked):
    original,source,target=inputs(tmp_path);target.mkdir()
    before=preserved(tmp_path)
    with LockFiles(tmp_path if locked=='parent' else target) as held:
        held.acquire()
        with no_bootstrap_writes():result=invoke(source,target)
    # The established native init/lock contract treats a held mutex as an
    # environment blocker (11.8 / code 5), not a stale model-basis conflict.
    assert result.exit_code==5 and preserved(tmp_path)==before
    assert result.as_dict()['summary']['bootstrap']=={'reason':'project_lock_busy','mutation_possible':False}


@pytest.mark.parametrize('case',CORPUS['cases'],ids=[c['id'] for c in CORPUS['cases']])
def test_independent_unsafe_archives_cannot_reach_target_writes(tmp_path,case):
    raw=base64.b64decode(case['zip_base64'],validate=True)
    assert sha256(raw).hexdigest()==case['sha256']
    source=tmp_path/'hostile.zip';source.write_bytes(raw);target=tmp_path/'target'
    before=preserved(tmp_path)
    with no_bootstrap_writes():result=invoke(source,target)
    assert result.exit_code==case['exit_code'] and result.as_dict()['result'] is None
    assert result.as_dict()['summary']['bundle_failure']['code']==case['code']
    assert preserved(tmp_path)==before





@pytest.mark.parametrize('cut', ['prepared', *PROJECT_UNITS, 'receipt-move', 'complete'])
@pytest.mark.parametrize('exists', [False,True])
def test_all_extraction_process_boundaries_remain_blocked(tmp_path,cut,exists):
    original,source,_=inputs(tmp_path)
    target=tmp_path/'target'
    if exists:target.mkdir()
    interrupt(source,target,cut)
    before=preserved(tmp_path)
    with no_bootstrap_writes():result=invoke(source,target)
    assert result.exit_code==5 and result.as_dict()['result'] is None
    assert preserved(tmp_path)==before
    fresh=tmp_path/'new-target'
    check_files(fresh,original,extraction.extract_bundle(original.source_bytes,fresh))

@pytest.mark.parametrize('failure',['zero-write','file-fsync','directory-fsync'])
def test_native_io_error_retains_guard_and_actual_evidence(tmp_path,monkeypatch,failure):
    original,source,_=inputs(tmp_path);target=tmp_path/'target'
    real_write,real_sync=os.write,os.fsync
    hit=[]
    def write(fd,raw):
        if not hit:hit.append('write');return 0
        return real_write(fd,raw)
    def sync(fd):
        import stat
        match=stat.S_ISDIR(os.fstat(fd).st_mode)==(failure=='directory-fsync')
        if match and not hit:hit.append('sync');raise OSError('injected durability failure')
        return real_sync(fd)
    with monkeypatch.context() as patch:
        patch.setattr(os,'write' if failure=='zero-write' else 'fsync',write if failure=='zero-write' else sync)
        result=invoke(source,target)
    assert hit and result.exit_code!=0
    before=preserved(tmp_path)
    with no_bootstrap_writes():again=invoke(source,target)
    assert again.exit_code==5 and preserved(tmp_path)==before

@pytest.mark.parametrize('damage', ['unknown-field', 'version', 'state', 'root-inode',
    'stage-inode', 'boolean-inode', 'duplicate-inode', 'unknown-path', 'missing-path',
    'traversal', 'wrong-units', 'duplicate-unit', 'reused', 'executable', 'oversized-payload',
    'boolean-size', 'entries-type', 'noncanonical', 'duplicate-key', 'oversized-journal', 'invalid-json'])
def test_invalid_record_cannot_authorize_any_extraction_write(tmp_path, damage):
    original, source, target = inputs(tmp_path)
    record, value = interrupt(source, target)
    entries = value['entries']; config = entries['specroad.json']
    if damage == 'unknown-field': value['execute'] = 'not executable'
    elif damage == 'version': value['format'] = 'specroad-bundle-bootstrap-v2'
    elif damage == 'state': value['state'] = 'complete'
    elif damage == 'root-inode': value['root_identity'][1] += 1
    elif damage == 'stage-inode': value['stage_identity'][1] += 1
    elif damage == 'boolean-inode': config['identity'][0] = True
    elif damage == 'duplicate-inode': config['identity'] = entries['profiles/core.json']['identity']
    elif damage == 'unknown-path': entries['foreign'] = dict(config)
    elif damage == 'missing-path': entries.pop('spec')
    elif damage == 'traversal': entries['../foreign'] = dict(config)
    elif damage == 'wrong-units': value['units'].reverse()
    elif damage == 'duplicate-unit': value['units'].append('specroad.json')
    elif damage == 'reused': value['reused_directories']['spec'] = entries['spec']
    elif damage == 'executable': config['mode'] = 0o755
    elif damage == 'oversized-payload': config['size'] = 1000000000
    elif damage == 'boolean-size': config['size'] = True
    elif damage == 'entries-type': value['entries'] = []
    raw = canonical_json_bytes(value)
    if damage == 'noncanonical': raw += b'\n'
    elif damage == 'duplicate-key': raw = b'{"state":"prepared",' + raw[1:]
    elif damage == 'oversized-journal': raw = b' ' * 1000000
    elif damage == 'invalid-json': raw = b'{broken'
    record.write_bytes(raw)
    before = preserved(tmp_path)
    with no_bootstrap_writes(): result = invoke(source, target)
    assert result.exit_code == 5 and result.as_dict()['result'] is None
    assert preserved(tmp_path) == before

@pytest.mark.parametrize('damage', ['bytes', 'inode', 'mode', 'hardlink', 'symlink',
    'extra-stage', 'extra-published', 'extra-root', 'missing', 'both-locations', 'order',
    'journal-hardlink', 'journal-symlink', 'receipt-conflict'])
def test_changed_or_ambiguous_actual_inventory_is_preserved(tmp_path, damage):
    original, source, target = inputs(tmp_path)
    record, value = interrupt(source, target, '.specroad')
    stage = target/io.STAGING; payload = stage/'profiles/core.json'
    if damage == 'bytes': payload.write_bytes(payload.read_bytes()+b'\n')
    elif damage == 'inode':
        replacement = payload.with_name('replacement'); replacement.write_bytes(payload.read_bytes()); replacement.replace(payload)
    elif damage == 'mode': payload.chmod(0o600)
    elif damage == 'hardlink': os.link(payload, tmp_path/'foreign-link')
    elif damage == 'symlink':
        foreign = tmp_path/'foreign'; payload.rename(foreign); payload.symlink_to(foreign)
    elif damage == 'extra-stage': (stage/'unlisted').write_bytes(b'foreign')
    elif damage == 'extra-published': (target/'.specroad/foreign').write_bytes(b'foreign')
    elif damage == 'extra-root': (target/'foreign').write_bytes(b'foreign')
    elif damage == 'missing': payload.unlink()
    elif damage == 'both-locations': (target/'profiles').mkdir()
    elif damage == 'order': (stage/'spec').rename(target/'spec')
    elif damage == 'journal-hardlink': os.link(record,tmp_path/'foreign-journal')
    elif damage == 'journal-symlink':
        foreign = tmp_path/'foreign-journal'; record.rename(foreign); record.symlink_to(foreign)
    elif damage == 'receipt-conflict': target.joinpath(*COMPLETED).mkdir()
    before = preserved(tmp_path)
    with no_bootstrap_writes(): result = invoke(source, target)
    assert result.exit_code == 5, result.as_dict()
    assert result.as_dict()['result'] is None and preserved(tmp_path) == before

@pytest.mark.parametrize('path', ['specroad.json','bundle-manifest.json','profiles/core.json'])
def test_rehashed_journal_cannot_replace_the_caller_bound_bundle(tmp_path, path):
    original, source, target = inputs(tmp_path)
    record, value = interrupt(source,target)
    payload = target/io.STAGING/path
    raw = payload.read_bytes()+b'\n'; payload.write_bytes(raw)
    value['entries'][path].update(size=len(raw),sha256=sha256(raw).hexdigest())
    record.write_bytes(canonical_json_bytes(value))
    before = preserved(tmp_path)
    with no_bootstrap_writes(): result=invoke(source,target,original.sha256)
    assert result.exit_code == 5 and preserved(tmp_path) == before

@pytest.mark.parametrize('where',['next-unit','root-alias','stage','published'])
def test_foreign_concurrent_writes_are_preserved_and_block_completion(tmp_path,monkeypatch,where):
    original,source,target=inputs(tmp_path)
    native=io.rename_new; foreign=None
    def interfere(function,source_fd,name,target_fd,destination):
        nonlocal foreign
        if destination=='profiles' and foreign is None:
            if where=='next-unit':
                (target/'profiles').mkdir();foreign=target/'profiles/foreign'
            elif where=='root-alias':foreign=target/'SPEC'
            elif where=='stage':foreign=target/io.STAGING/'foreign'
            else:foreign=target/'.specroad/foreign'
            foreign.write_bytes(b'not owned by extraction')
            if where=='next-unit':return native(function,source_fd,name,target_fd,destination)
        return native(function,source_fd,name,target_fd,destination)
    with monkeypatch.context() as active:
        active.setattr(io,'rename_new',interfere)
        result=invoke(source,target)
    assert foreign is not None and result.exit_code in (5,6) and result.as_dict()['result'] is None
    assert foreign.read_bytes()==b'not owned by extraction'
    assert not (target/'specroad.json').exists()
    before=preserved(tmp_path)
    with no_bootstrap_writes():again=invoke(source,target)
    assert again.exit_code==5 and preserved(tmp_path)==before

@pytest.mark.parametrize('point',['validation','publication','completion'])
def test_changed_input_is_rechecked_during_both_fresh_and_replayed_publication(tmp_path,monkeypatch,point):
    original,source,target=inputs(tmp_path)
    changed=False
    def change():
        nonlocal changed
        if not changed:source.write_bytes(b'changed input');changed=True
    native_prepare,native_restore=io.BootstrapTree.prepare,extraction.restore_inventory
    native_move,native_finish=io.rename_new,io.BootstrapTree.retain_completed
    def prepared(tree,*args,**kwargs):
        native_prepare(tree,*args,**kwargs)
        if point=='validation':change()
    def restored(*args,**kwargs):
        native_restore(*args,**kwargs)
        if point=='validation':change()
    def moved(*args):
        native_move(*args)
        if point=='publication':change()
    def finished(tree):
        native_finish(tree)
        if point=='completion':change()
    with monkeypatch.context() as active:
        active.setattr(io.BootstrapTree,'prepare',prepared)
        active.setattr(extraction,'restore_inventory',restored)
        active.setattr(io,'rename_new',moved)
        active.setattr(io.BootstrapTree,'retain_completed',finished)
        result=invoke(source,target)
    assert changed and result.exit_code==6 and result.as_dict()['result'] is None,result.as_dict()
    assert target.exists()
    source.write_bytes(original.source_bytes)
    result=invoke(source,target,original.sha256)
    assert result.exit_code==5,result.as_dict()
    fresh=tmp_path/'new-target'
    fresh_result=invoke(source,fresh,original.sha256)
    assert fresh_result.exit_code==0
    check_files(fresh,original,fresh_result.as_dict()['result'])

def test_foreign_name_after_receipt_retention_cannot_be_reported_as_success(tmp_path,monkeypatch):
    original,source,target=inputs(tmp_path)
    native=io.BootstrapTree.retain_completed;changed=False
    def finish(tree):
        nonlocal changed
        native(tree)
        if not changed:
            (target/'foreign').write_bytes(b'preserve concurrent data');changed=True
    with monkeypatch.context() as active:
        active.setattr(io.BootstrapTree,'retain_completed',finish)
        result=invoke(source,target)
    assert changed and result.exit_code==6 and result.as_dict()['result'] is None
    assert (target/'foreign').read_bytes()==b'preserve concurrent data'
    assert all((target/p).read_bytes()==raw for p,raw in original.files.items())
    assert (target.joinpath(*COMPLETED)/'journal.json').is_file()
    before=preserved(tmp_path)
    with no_bootstrap_writes():again=invoke(source,target)
    assert again.exit_code==5 and preserved(tmp_path)==before
