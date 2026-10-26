"""15.l.W: real authorized initial Restore publication and original evidence.

Host authorities below are synthetic. No human release/review is asserted;
interrupted execution must remain blocked until separate explicit recovery.
"""
from base64 import b64decode
from hashlib import sha256
import json
import os

import pytest

from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.changes._lock_files import LockFiles
from specroad.changes.locking import project_lock
from specroad.changes.recovery_values import RecoveryAuthority
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.paths import artifact_path
from specroad.recovery import RestoreError, execute_restore
from specroad.recovery._execution_store import RestoreStore
from specroad.security import ProjectBoundary
from specroad.storage.operational_preflight import observe_operational_preflight
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.restore import restore_case, plan_for
from support.records import record_value, ref
from support.domain import domain_value
from support.scopes import descriptor

ACTOR = {'actor_type': 'human', 'actor_id': 'synthetic-restore-operator'}
ALLOW = RecoveryAuthority('synthetic-restore-authorizer', '1', lambda request: True)


def selected(plan, paths):
    entries = plan.data['inventory']['entries']
    return canonical_json_bytes({'format_version': 'restore-journal-selection-v1',
        'restore_plan_sha256': plan.data['restore_plan_sha256'], 'entries': [
            {'path': p, 'sha256': canonical_json_sha256([r for r in entries
                if r['path'] == p or r['path'].startswith(p + '/')])} for p in sorted(paths)]})


def execute(plan, **kwargs):
    return execute_restore(plan.source_bytes, **{'expected_target_root': plan.data['expected_target_root'],
        'authority': ALLOW, 'actor': ACTOR, 'request_id': 'restore-test', **kwargs})


def files(plan, table):
    objects = {r['sha256']: b64decode(r['data_base64']) for r in plan.data['objects']}
    return {r['path']: objects[r['sha256']] for r in plan.data[table]['entries']}


def damage(options, original):
    path = next(p for p in original if p.startswith('spec/goals/'))
    put(options['project_root'], path, b'\x00\xff{not JSON\r\n')
    return path


@pytest.mark.parametrize('kind', ['project_bundle', 'baseline'])
@pytest.mark.parametrize('journal', ['tree', 'empty_file', 'empty_directory', 'absent'])
def test_initial_restore_reaches_exact_full_target_and_retains_selected_originals(tmp_path, kind, journal, monkeypatch):
    options, original, _ = restore_case(tmp_path, kind)
    root = options['project_root']
    damaged = damage(options, original)
    journal_path = '.specroad/transactions/corrupt'
    if journal == 'tree':
        for suffix, raw in [('journal.json', b'{broken'), ('before/0', b'old\xff'),
                            ('staging/0', b'new\x00'), ('extra', b'')]:
            put(root, journal_path + '/' + suffix, raw)
        (root / journal_path / 'empty').mkdir()
    elif journal == 'empty_file':
        journal_path = '.specroad/recovery/corrupt'
        put(root, journal_path, b'')
    elif journal == 'empty_directory':
        (root / journal_path).mkdir(parents=True)
    plan = plan_for(options)
    selection = None if journal == 'absent' else selected(plan, [journal_path])
    backup = files(plan, 'backup')
    target = files(plan, 'target')
    published, archived = [], []
    native_publish, native_archive = RestoreStore.publish, RestoreStore.archive

    def publish(store, staged, path, raw):
        # Every target, including unchanged resources, was staged before the
        # first normative mutation; every original backup survived readback.
        if not published:
            active = next(p for p in store.own if p.endswith('/intent.json')).rsplit('/', 1)[0]
            intent = json.loads((root / active / 'intent.json').read_bytes())
            assert intent['original_plan'] == plan.data
            assert intent['request']['affected_journals'] == (json.loads(selection) if selection else {
                'format_version': 'restore-journal-selection-v1',
                'restore_plan_sha256': plan.data['restore_plan_sha256'], 'entries': []})
            staged_rows = [r for r in intent['own_files'] if r['path'].startswith(active + '/staging/')]
            assert len(staged_rows) == len(target)
            assert sorted(r['sha256'] for r in staged_rows) == sorted(sha256(b).hexdigest() for b in target.values())
            for row in staged_rows:
                assert sha256((root / row['path']).read_bytes()).hexdigest() == row['sha256']
            archive = root / '.specroad/recovery/archive' / intent['execution_id']
            assert (archive / 'plan.json').read_bytes() == plan.source_bytes
            assert json.loads((archive / 'manifest.json').read_bytes())['inventory'] == plan.data['inventory']
            for content in backup.values():
                assert (archive / 'objects' / sha256(content).hexdigest()).read_bytes() == content
            assert not (archive / 'completed.json').exists()
            if journal != 'absent':
                assert (root / journal_path).exists()
        published.append(path)
        return native_publish(store, staged, path, raw)

    def archive(store, path, destination):
        # No selected old entry is released before the exact target AND audit.
        assert all((root / p).read_bytes() == raw for p, raw in target.items())
        assert list((root / '.specroad/recovery/archive').glob('*/completed.json'))
        with LockFiles(root) as observed:
            assert any(p.startswith('.specroad/recovery/restore-') for p in observed.journal_entries())
        archived.append((path, destination))
        return native_archive(store, path, destination)

    monkeypatch.setattr(RestoreStore, 'publish', publish)
    monkeypatch.setattr(RestoreStore, 'archive', archive)
    result = execute(plan, affected_journals=selection).data
    assert result['result'] == 'restored' and not result['recovery_required']
    assert published == sorted(published) and damaged in published
    actual = InspectionSnapshot(root, None, include_archive_objects=True)
    assert actual.raw == target
    assert actual.model.manifest(actual.model.artifacts, descriptor('project')).sha256 == plan.data['expected_target_root']
    audit = json.loads((root / result['audit_path']).read_bytes())
    assert audit['request']['restore_plan_sha256'] == plan.data['restore_plan_sha256']
    assert audit['request']['plan_bytes_sha256'] == plan.sha256
    assert audit['request']['backup_sha256'] == plan.data['backup']['sha256']
    assert audit['authority_id'] == ALLOW.authority_id and audit['request']['actor'] == ACTOR
    archive_root = (root / result['audit_path']).parent
    for p, raw in backup.items():
        assert (archive_root / 'objects' / sha256(raw).hexdigest()).read_bytes() == raw
    if journal != 'absent':
        assert not (root / journal_path).exists()
        moved = archive_root / 'originals/0'
        for row in plan.data['inventory']['entries']:
            if row['path'] == journal_path or row['path'].startswith(journal_path + '/'):
                path = moved if row['path'] == journal_path else moved / row['path'][len(journal_path) + 1:]
                if row['kind'] == 'directory': assert path.is_dir()
                else: assert path.read_bytes() == backup[row['path']]
    with LockFiles(root) as observed:
        assert observed.read_record()[0] is None and observed.journal_entries() == ()
    assert not observe_operational_preflight(ProjectBoundary(root))['recovery_required']
    assert len(archived) == (1 if journal == 'absent' else 2)


@pytest.mark.parametrize('selection', ['omitted', 'empty', 'one'])
def test_unselected_active_entries_prevent_even_operational_writes(tmp_path, selection):
    options, original, _ = restore_case(tmp_path)
    damage(options, original)
    paths = ['.specroad/transactions/first', '.specroad/recovery/second']
    for path in paths: put(options['project_root'], path, b'{broken')
    plan = plan_for(options)
    raw = None if selection == 'omitted' else selected(plan, [] if selection == 'empty' else paths[:1])
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError) as failure:
        execute(plan, affected_journals=raw)
    assert failure.value.exit_code == 5
    assert failure.value.diagnostic()['recovery_required']
    assert not failure.value.diagnostic()['mutation_possible'] and inventory(tmp_path) == before


@pytest.mark.parametrize('fault', ['denied', 'non_bool', 'mutated', 'no_authority', 'target', 'ai_request'])
def test_initial_authority_and_independent_target_are_mandatory_and_write_free(tmp_path, fault):
    options, _, _ = restore_case(tmp_path)
    plan = plan_for(options)
    kwargs, code = {}, 7
    if fault == 'denied': kwargs['authority'] = RecoveryAuthority('test', '1', lambda r: False)
    elif fault == 'non_bool': kwargs['authority'] = RecoveryAuthority('test', '1', lambda r: 1)
    elif fault == 'mutated':
        def mutate(request):
            request['affected_journals']['entries'].append({'path': 'forged'})
            return True
        kwargs['authority'] = RecoveryAuthority('test', '1', mutate)
    elif fault == 'no_authority': kwargs['authority'], code = None, 2
    elif fault == 'target': kwargs['expected_target_root'], code = '0' * 64, 6
    else: kwargs.update(actor={'actor_type': 'ai', 'actor_id': 'synthetic'}, request_id=None); code = 2
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError) as failure:
        execute(plan, **kwargs)
    assert failure.value.exit_code == code and inventory(tmp_path) == before
    assert not failure.value.mutation_possible


def test_revalidation_and_authority_under_kernel_mutex_precede_owner_creation(tmp_path):
    options, _, _ = restore_case(tmp_path)
    root = options['project_root']; plan = plan_for(options)
    calls = []
    def check(request):
        calls.append(request)
        if len(calls) == 2:
            with LockFiles(root) as concurrent:
                with pytest.raises(Exception) as busy:
                    concurrent.acquire()
                assert busy.value.reason == 'project_lock_busy'
            assert not (root / '.specroad').exists()
            return False
        return True
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError) as failure:
        execute(plan, authority=RecoveryAuthority('test', '1', check))
    assert len(calls) == 2 and failure.value.exit_code == 7
    assert not failure.value.mutation_possible and inventory(tmp_path) == before


@pytest.mark.parametrize('which', ['source', 'current'])
def test_late_authorizer_input_change_is_detected_before_first_restore_write(tmp_path, which):
    options, original, source = restore_case(tmp_path)
    plan = plan_for(options); calls = []
    def check(request):
        calls.append(request)
        if len(calls) == 2:
            if which == 'source': put(options['source_root'], options['source_path'], source + b'changed')
            else: damage(options, original)
        return True
    with pytest.raises(RestoreError) as failure:
        execute(plan, authority=RecoveryAuthority('test', '1', check))
    assert failure.value.exit_code == 6 and not failure.value.mutation_possible
    assert not (options['project_root'] / '.specroad').exists()


def test_existing_owner_is_not_removed_or_interpreted_as_permission(tmp_path):
    options, _, _ = restore_case(tmp_path)
    plan = plan_for(options); root = options['project_root']
    with project_lock(root, kind='recovery', command='recover run', project_id=plan.data['project_id'], transaction_id='existing'):
        before = inventory(root)
        with no_write_attempts(), pytest.raises(RestoreError) as failure:
            execute(plan)
        assert failure.value.exit_code == 5 and failure.value.recovery_required
        assert inventory(root) == before


@pytest.mark.parametrize('when', ['before', 'after'])
def test_publication_io_failure_retains_active_barrier_original_backup_and_actual_bytes(tmp_path, monkeypatch, when):
    options, original, _ = restore_case(tmp_path)
    root = options['project_root']; path = damage(options, original)
    old = (root / path).read_bytes()
    put(root, '.specroad/transactions/corrupt/journal.json', b'{original')
    plan = plan_for(options)
    native = os.replace
    def interrupted(*args, **kwargs):
        if when == 'after': native(*args, **kwargs)
        raise OSError(5, 'synthetic publication failure')
    monkeypatch.setattr(os, 'replace', interrupted)
    with pytest.raises(RestoreError) as failure:
        execute(plan, affected_journals=selected(plan, ['.specroad/transactions/corrupt']))
    assert failure.value.exit_code == 5 and failure.value.mutation_possible and failure.value.recovery_required
    assert (root / path).read_bytes() == (old if when == 'before' else original[path])
    assert (root / '.specroad/transactions/corrupt/journal.json').read_bytes() == b'{original'
    archives = list((root / '.specroad/recovery/archive').iterdir())
    assert len(archives) == 1 and (archives[0] / 'objects' / sha256(old).hexdigest()).read_bytes() == old
    assert not (archives[0] / 'completed.json').exists()
    observed = observe_operational_preflight(ProjectBoundary(root))
    assert observed['recovery_required'] and any('/restore-' in p for p in observed['unresolved_paths'])
    # R adds the separately authorized recovery operation to the same API.
    # It must preserve the original failure evidence and never publish forward
    # from a partial state. The W assertions above remain unchanged.
    monkeypatch.setattr(os, 'replace', native)
    result = execute(plan, affected_journals=selected(plan, ['.specroad/transactions/corrupt'])).data
    assert result['result'] == ('rolled_back' if when == 'before' else 'restored')
    assert result['recovery_required'] == (when == 'before')
    assert (root / path).read_bytes() == (old if when == 'before' else original[path])
    assert (archives[0] / 'objects' / sha256(old).hexdigest()).read_bytes() == old


@pytest.mark.parametrize('fault,code', [('plan', 6), ('subtree', 6), ('raw_hash', 6),
    ('duplicate', 3), ('unsorted', 3), ('extra', 3), ('bom', 3), ('invalid_hash', 3),
    ('root', 7), ('locks', 7), ('receipt', 7), ('audit', 7), ('archive', 7), ('traversal', 7)])
def test_explicit_selection_never_expands_into_a_different_binding_or_area(tmp_path, fault, code):
    options, _, _ = restore_case(tmp_path)
    paths = ['.specroad/transactions/a', '.specroad/transactions/b']
    for path in paths: put(options['project_root'], path + '/journal.json', b'{broken')
    plan = plan_for(options)
    value = json.loads(selected(plan, paths))
    if fault == 'plan': value['restore_plan_sha256'] = '0' * 64
    elif fault == 'subtree': value['entries'][0]['sha256'] = '0' * 64
    elif fault == 'raw_hash': value['entries'][0]['sha256'] = sha256(b'{broken').hexdigest()
    elif fault == 'duplicate': value['entries'].append(value['entries'][0])
    elif fault == 'unsorted': value['entries'].reverse()
    elif fault == 'extra': value['approved'] = True
    elif fault == 'invalid_hash': value['entries'][0]['sha256'] = 'X' * 64
    elif fault != 'bom':
        value['entries'][0]['path'] = {'root': '.specroad/transactions', 'locks': '.specroad/locks/project.json',
            'receipt': '.specroad/transactions/receipts', 'audit': '.specroad/recovery/transaction-audit',
            'archive': '.specroad/recovery/archive', 'traversal': '../outside'}[fault]
    raw = canonical_json_bytes(value)
    if fault == 'bom': raw = b'\xef\xbb\xbf' + raw
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError) as failure:
        execute(plan, affected_journals=raw)
    assert failure.value.exit_code == code and not failure.value.mutation_possible
    assert inventory(tmp_path) == before


def test_exact_request_binds_authority_and_original_state_even_for_zero_model_effects(tmp_path):
    options, _, _ = restore_case(tmp_path)
    root = options['project_root']
    put(root, '.specroad/recovery/damaged', b'')
    plan = plan_for(options)
    observed = []
    def check(request):
        observed.append(canonical_json_bytes(request))
        return True
    result = execute(plan, authority=RecoveryAuthority('test', 'v2', check),
                     affected_journals=selected(plan, ['.specroad/recovery/damaged'])).data
    assert len(observed) == 3 and len(set(observed)) == 1
    assert result['normative_paths'] == [] and result['expected_target_root'] == plan.data['expected_target_root']
    with LockFiles(root) as access:
        assert access.journal_entries() == ()


def test_unpublished_mutable_addition_is_removed_only_after_exact_backup(tmp_path):
    options, _, _ = restore_case(tmp_path)
    value = domain_value('goal', id=ref('GOAL', '1'))
    path = artifact_path('goal', value['id'], 'SR')
    raw = canonical_json_bytes(value)
    put(options['project_root'], path, raw)
    plan = plan_for(options)
    assert files(plan, 'backup')[path] == raw and path not in files(plan, 'target')
    result = execute(plan).data
    assert not (options['project_root'] / path).exists() and result['normative_paths'] == [path]
    archive = (options['project_root'] / result['audit_path']).parent
    assert (archive / 'objects' / sha256(raw).hexdigest()).read_bytes() == raw


def test_foreign_bytes_inside_own_archive_are_not_an_inventory_exception(tmp_path):
    options, original, _ = restore_case(tmp_path)
    root = options['project_root']; damaged = damage(options, original)
    before_image = (root / damaged).read_bytes(); plan = plan_for(options)
    calls = []
    def check(request):
        calls.append(1)
        if len(calls) == 3:
            archive = root / '.specroad/recovery/archive' / canonical_json_sha256(request)
            (archive / 'foreign').write_bytes(b'unbound foreign bytes')
        return True
    with pytest.raises(RestoreError) as failure:
        execute(plan, authority=RecoveryAuthority('test', '1', check))
    assert failure.value.exit_code == 6 and failure.value.recovery_required and failure.value.mutation_possible
    assert (root / damaged).read_bytes() == before_image
    assert list((root / '.specroad/recovery/archive').glob('*/foreign'))
    assert observe_operational_preflight(ProjectBoundary(root))['recovery_required']


@pytest.mark.parametrize('reuse_request', [False, True])
def test_completed_native_receipts_remain_byte_exact_at_their_original_paths(tmp_path, reuse_request):
    from test_bundle_receipts import completed, receipts
    from specroad.bundles import prepare_project_bundle
    from specroad.recovery import prepare_restore_plan
    root, origin = tmp_path / 'current', tmp_path / 'origin'
    completed(root)
    document = record_value('document')
    put(root, artifact_path('document', document['id'], 'SR'), canonical_json_bytes(document))
    model = InspectionSnapshot(root, None, include_archive_objects=True)
    for path, raw in model.raw.items(): put(origin, path, raw)
    source = prepare_project_bundle(origin)
    put(origin, 'source.zip', source.source_bytes)
    saved = receipts(root)
    damaged = next(p for p in model.raw if p.startswith('spec/goals/'))
    put(root, damaged, b'{damaged')
    plan = prepare_restore_plan(root, source_root=origin, source_path='source.zip', source_kind='project_bundle')
    if reuse_request:
        before = inventory(tmp_path)
        with no_write_attempts(), pytest.raises(RestoreError) as failure:
            execute(plan, request_id='portable-request')
        assert failure.value.exit_code == 6 and inventory(tmp_path) == before
    else:
        result = execute(plan).data
        assert result['result'] == 'restored' and receipts(root) == saved
        assert all((root / path).read_bytes() == raw for path, raw in model.raw.items())
