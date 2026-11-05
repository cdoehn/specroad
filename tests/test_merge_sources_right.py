"""17.a.R: complete-source admission, immutable observations and no migration."""
import json
import os

import pytest

from specroad.archive import build_baseline_manifest
from specroad.bundles import BundleError, prepare_partial_bundle, prepare_project_bundle
from specroad.bundles.extraction import extract_bundle
from specroad.bundles._extraction_record import COMPLETED
from specroad.merge import SourceRequest, SourceSnapshot, load_merge_sources
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.model.model_manifest import ProjectReadBinding
from specroad.model.paths import artifact_path
from specroad.security import ProjectBoundary, SafetyViolation
from specroad.storage.archive import encode_archive
from support.domain import domain_value
from support.git_objects import GitFixture
from support.model import configuration_value, put
from support.read_only import inventory
from support.records import record_value, ref
from support.scopes import descriptor
from test_baseline_manifest import baseline_inputs
from test_configured_baseline import variant_inputs
from test_merge_sources import KINDS, read_only_sources, sources
from test_partial_bundle import project as partial_project, scope
from test_project_bundle import project, baseline_project


def archived(root, inputs):
    root.mkdir()
    snapshot = build_baseline_manifest(**inputs, baseline_id=ref('BASE'))
    record = record_value('baseline', id=ref('BASE'), **{k: snapshot.data[k] for k in
        ('scope_descriptor', 'manifest', 'model_root_sha256', 'configuration_hash', 'profiles', 'tool_version')})
    for item in snapshot.objects:
        put(root, item.reference.path, item.content)
    put(root, artifact_path('baseline', record['id'], 'SR'), canonical_json_bytes(record))
    return SourceRequest(root, 'baseline', record['id'])


@pytest.mark.parametrize('value', [None, True, 12, b'root', [], {}, '', ' ', 'bad\0root', '\ud800'])
def test_invalid_root_fails_before_opening_a_filesystem_boundary(monkeypatch, value):
    monkeypatch.setattr(ProjectBoundary, '__init__', lambda *a: pytest.fail('Invalid root was observed'))
    with read_only_sources(), pytest.raises(ModelError):
        SourceSnapshot(SourceRequest(value))


@pytest.mark.parametrize('kind,reference', [('local', 'main'), ('bundle', 'main'),
    ('git', None), ('baseline', None), ('baseline', b'record'), ('git', ''), ('git', '\ud800'),
    ('git', 'bad\0ref'), ('foreign', None), (None, None), ([], None)])
def test_selectors_are_typed_and_never_silently_default_to_a_local_source(tmp_path, kind, reference):
    before = inventory(tmp_path)
    with read_only_sources(), pytest.raises(ModelError):
        SourceSnapshot(SourceRequest(tmp_path, kind, reference))
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('position', range(3))
def test_foreign_identity_is_rejected_for_each_source_kind_and_role(tmp_path, kind, position):
    root = tmp_path / 'source'; project(root)
    if kind == 'baseline':
        args = baseline_inputs(configuration=configuration_value(project_id='foreign'), values=[domain_value('goal')],
                               scope=descriptor('project'), attachment=None)
        args['binding'] = ProjectReadBinding('foreign', '/fixture/foreign', (1, 2))
        foreign = archived(tmp_path / 'archive', args)
    else:
        other = tmp_path / 'foreign'; project(other)
        value = json.loads((other / 'specroad.json').read_bytes()); value['project_id'] = 'foreign'
        put(other, 'specroad.json', canonical_json_bytes(value))
        bundle = prepare_project_bundle(other)
        if kind == 'local': foreign = SourceRequest(other)
        elif kind == 'git':
            git = GitFixture(tmp_path / 'git'); commit = git.commit(bundle.files)
            foreign = SourceRequest(git.root, 'git', commit)
        else:
            filename = tmp_path / 'foreign.zip'; filename.write_bytes(bundle.source_bytes)
            foreign = SourceRequest(filename, 'bundle')
    selected = [SourceRequest(root)] * 3; selected[position] = foreign
    before = inventory(tmp_path)
    with read_only_sources(), pytest.raises(ModelError) as error:
        load_merge_sources(*selected)
    assert error.value.reason == 'merge_project_mismatch'
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('version', ['0.1.0', '99.0.0'])
def test_unsupported_input_is_not_implicitly_migrated_or_supplemented(tmp_path, kind, version):
    root = tmp_path / 'source'; snapshot = project(root)
    files = dict(snapshot.raw)
    value = json.loads(files['specroad.json']); value['schema_version'] = version
    files['specroad.json'] = canonical_json_bytes(value)
    if kind == 'local':
        put(root, 'specroad.json', files['specroad.json']); request = SourceRequest(root)
    elif kind == 'git':
        git = GitFixture(tmp_path / 'git'); commit = git.commit(files)
        # A valid mutable worktree cannot rescue the selected old commit.
        for path, raw in snapshot.raw.items(): put(git.root, path, raw)
        request = SourceRequest(git.root, 'git', commit)
    elif kind == 'bundle':
        metadata = prepare_project_bundle(root).manifest; metadata.pop('entries')
        metadata['schema_version'] = version
        filename = tmp_path / 'old.zip'
        filename.write_bytes(encode_archive('bundle-manifest.json', metadata, files))
        request = SourceRequest(filename, 'bundle')
    else:
        origin = tmp_path / 'archive'; operation = baseline_project(origin)
        record = operation['record']; record['schema_version'] = version
        put(origin, artifact_path('baseline', record['id'], 'SR'), canonical_json_bytes(record))
        request = SourceRequest(origin, 'baseline', record['id'])
    before = inventory(tmp_path)
    with read_only_sources(), pytest.raises((ModelError, BundleError)) as error:
        SourceSnapshot(request)
    assert error.value.reason in ('unsupported_schema_version', 'unsupported_bundle_version')
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('selection', ['document', 'release'])
def test_partial_markers_and_verified_partial_bundles_never_become_full_sources(tmp_path, kind, selection):
    origin = tmp_path / 'origin'; partial_project(origin, selection)
    partial = prepare_partial_bundle(origin, scope(selection))
    if kind == 'bundle':
        filename = tmp_path / 'partial.zip'; filename.write_bytes(partial.source_bytes)
        request = SourceRequest(filename, 'bundle')
    elif kind == 'git':
        git = GitFixture(tmp_path / 'git')
        commit = git.commit({**partial.files, 'bundle-manifest.json': partial.manifest_bytes})
        request = SourceRequest(git.root, 'git', commit)
    elif kind == 'baseline':
        archive = tmp_path / 'archive'; operation = baseline_project(archive)
        put(archive, 'bundle-manifest.json', partial.manifest_bytes)
        request = SourceRequest(archive, 'baseline', operation['record']['id'])
    else:
        put(origin, 'bundle-manifest.json', partial.manifest_bytes)
        request = SourceRequest(origin)
    before = inventory(tmp_path)
    with read_only_sources(), pytest.raises((ModelError, BundleError, SafetyViolation)):
        SourceSnapshot(request)
    assert inventory(tmp_path) == before


def test_configured_baseline_cannot_silently_become_a_full_project(tmp_path):
    request = archived(tmp_path / 'archive', variant_inputs())
    before = inventory(tmp_path)
    with read_only_sources(), pytest.raises(ModelError) as error:
        SourceSnapshot(request)
    assert error.value.reason == 'merge_complete_project_required'
    assert inventory(tmp_path) == before


def test_baseline_retains_its_archived_profile_chain_without_changing_configuration(tmp_path):
    inputs = baseline_inputs(scope=descriptor('project'), attachment=None, values=[domain_value('goal')])
    request = archived(tmp_path / 'archive', inputs)
    record_path = artifact_path('baseline', request.reference, 'SR')
    record = json.loads((request.root / record_path).read_bytes())
    before = inventory(tmp_path)
    with read_only_sources(): source = SourceSnapshot(request)
    assert source.binding['model_root_sha256'] == record['model_root_sha256']
    assert source.binding['baseline']['profile_keys'] == ['core@0.2.0', 'product@0.2.0']
    assert json.loads(source.files['specroad.json'])['profiles'] == []
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('change', ['removed', 'replaced'])
def test_git_cannot_erase_retained_partial_extraction_proof(tmp_path, change):
    origin = tmp_path / 'origin'; partial_project(origin)
    partial = prepare_partial_bundle(origin, scope())
    target = tmp_path / 'extracted'; extract_bundle(partial.source_bytes, target)
    proof_path = '/'.join((*COMPLETED, 'journal.json'))
    files = dict(partial.files); files[proof_path] = (target / proof_path).read_bytes()
    if change == 'replaced': files['bundle-manifest.json'] = prepare_project_bundle(origin).manifest_bytes
    git = GitFixture(tmp_path / 'git'); commit = git.commit(files)
    before = git.capture()
    with read_only_sources(), pytest.raises(SafetyViolation):
        SourceSnapshot(SourceRequest(git.root, 'git', commit))
    assert git.capture() == before


def test_git_accepts_a_completed_full_extraction_without_consulting_checkout(tmp_path):
    origin = tmp_path / 'origin'; project(origin)
    full = prepare_project_bundle(origin)
    target = tmp_path / 'extracted'; extract_bundle(full.source_bytes, target)
    files = {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob('*') if p.is_file()}
    git = GitFixture(tmp_path / 'git'); commit = git.commit(files)
    before = git.capture()
    with read_only_sources(): result = SourceSnapshot(SourceRequest(git.root, 'git', commit))
    assert result.files == full.files and git.capture() == before


@pytest.mark.parametrize('kind', KINDS)
def test_first_source_is_rechecked_after_the_third_source_was_loaded(tmp_path, monkeypatch, kind):
    requests, _, record, git = sources(tmp_path)
    other = tmp_path / 'third'; project(other)
    selected = requests[kind]
    if kind == 'local': target = selected.root / 'specroad.json'
    elif kind == 'baseline': target = selected.root / artifact_path('baseline', record['id'], 'SR')
    elif kind == 'bundle': target = selected.root
    else: target = git.git / 'objects' / selected.reference[:2] / selected.reference[2:]
    original = target.read_bytes(); times = target.stat()
    read = ProjectBoundary.read_bytes; changed = False
    def reading(boundary, path):
        nonlocal changed
        raw = read(boundary, path)
        if boundary.root == other and path == 'specroad.json' and not changed:
            changed = True
            if kind == 'git': target.unlink()
            else:
                # Same size and timestamp must not disguise changed input bytes.
                target.write_bytes(original[:-1] + (b' ' if original[-1:] != b' ' else b'\n'))
                os.utime(target, ns=(times.st_atime_ns, times.st_mtime_ns))
        return raw
    monkeypatch.setattr(ProjectBoundary, 'read_bytes', reading)
    with pytest.raises((ModelError, BundleError)):
        load_merge_sources(selected, requests['local'], SourceRequest(other))
    assert changed
    assert not target.exists() if kind == 'git' else target.read_bytes() != original


def test_moving_git_ref_during_other_source_capture_does_not_rebind_the_selected_commit(tmp_path, monkeypatch):
    root = tmp_path / 'source'; model = project(root)
    git = GitFixture(tmp_path / 'git'); first = git.commit(model.raw)
    changed = dict(model.raw); changed['specroad.json'] += b'\n'
    second = git.commit(changed, parent=first, ref=None)
    read = ProjectBoundary.read_bytes; moved = False
    def reading(boundary, path):
        nonlocal moved
        raw = read(boundary, path)
        if boundary.root == root and not moved:
            git.ref('refs/heads/main', second); moved = True
        return raw
    monkeypatch.setattr(ProjectBoundary, 'read_bytes', reading)
    result = load_merge_sources(SourceRequest(git.root, 'git', 'main'), SourceRequest(root), SourceRequest(root))
    assert moved and result.base.commit_id == first and result.base.files == model.raw


@pytest.mark.parametrize('change', ['missing', 'corrupt', 'symlink', 'gitlink'])
def test_git_attachment_must_be_the_bound_regular_blob(tmp_path, change):
    root = tmp_path / 'source'; snapshot = project(root)
    files = dict(snapshot.raw); path = 'attachments/owned.bin'
    if change == 'missing': del files[path]
    elif change == 'corrupt': files[path] = b'wrong bytes'
    elif change == 'symlink': files[path] = ('120000', b'../../source/attachments/owned.bin')
    else: files[path] = ('160000', '1' * 40)
    git = GitFixture(tmp_path / 'git'); commit = git.commit(files)
    before = inventory(tmp_path)
    with read_only_sources(), pytest.raises((ModelError, BundleError, SafetyViolation)):
        SourceSnapshot(SourceRequest(git.root, 'git', commit))
    assert inventory(tmp_path) == before


def test_qualified_legacy_originals_are_owned_exactly_in_all_current_full_sources(tmp_path):
    from support.legacy_manifest import migrated, write_files, MANIFEST
    old, files, _ = migrated()
    root = tmp_path / 'source'; write_files(root, files)
    bundle = prepare_project_bundle(root)
    filename = tmp_path / 'project.zip'; filename.write_bytes(bundle.source_bytes)
    git = GitFixture(tmp_path / 'git'); commit = git.commit(files)
    before = inventory(tmp_path)
    with read_only_sources():
        result = load_merge_sources(SourceRequest(root), SourceRequest(git.root, 'git', commit),
                                    SourceRequest(filename, 'bundle'))
    registered = json.loads(files[MANIFEST])['entries']
    for source in (result.base, result.ours, result.theirs):
        assert source.files == bundle.files
        assert source.binding['model_root_sha256'] == bundle.manifest['bundle_model_root_sha256']
        for row in registered:
            assert source.files[row['path']] == files[row['path']]
        assert all(source.files[path] == raw for path, raw in old.items() if path.startswith('archive/'))
    assert inventory(tmp_path) == before
