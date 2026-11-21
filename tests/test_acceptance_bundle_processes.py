"""R-40..R-43 across actual fresh CLI processes and on-disk extraction."""
from hashlib import sha256
from io import BytesIO
import json
from zipfile import ZipFile
import pytest

from specroad.bundles import prepare_project_bundle, prepare_partial_bundle
from specroad.model.canonical import canonical_json_bytes as jcs
from support.languages import small_restore_registry
from support.processes import run_cli
from support.read_only import inventory
from test_project_bundle import project as full_project
from test_partial_bundle import project as partial_project, scope
from test_work_archive import foreign_zip


@pytest.fixture(scope='module')
def archives(tmp_path_factory):
    base = tmp_path_factory.mktemp('acceptance-bundles')
    values = []
    for kind in ('project', 'document', 'release'):
        root = base / kind
        if kind == 'project':
            full_project(root, language_registry=small_restore_registry())
            original = prepare_project_bundle(root)
        else:
            partial_project(root, kind)
            original = prepare_partial_bundle(root, scope(kind))
        values.append((kind, original.source_bytes, original.manifest_bytes, tuple(original.files.items())))
    return tuple(values)


@pytest.mark.parametrize('kind', ['project', 'document', 'release'])
def test_public_verify_and_extract_keep_exact_nonrecursive_inventory_and_partial_write_boundary(archives, tmp_path, kind):
    _, raw, manifest_bytes, files = next(row for row in archives if row[0] == kind)
    manifest = json.loads(manifest_bytes)
    source = tmp_path / 'input.zip'; source.write_bytes(raw)
    before = inventory(tmp_path)
    verified = run_cli(['bundle', 'verify', str(source), '--expected-sha256', sha256(raw).hexdigest(), '--format=json'], tmp_path, capture=True)
    assert verified.returncode == 0, verified.stderr
    data = json.loads(verified.stdout)['result']
    assert data['manifest'] == manifest and data['external_hash_verified'] and data['model_root_verified']
    assert not data['creator_authenticated'] and not data['approval_granted']
    assert inventory(tmp_path) == before
    target = tmp_path / 'extracted'
    extracted = run_cli(['bundle', 'extract', str(source), '--expected-sha256', sha256(raw).hexdigest(),
                         '--output', str(target), '--format=json'], tmp_path, capture=True)
    assert extracted.returncode == 0, extracted.stderr
    report = json.loads(extracted.stdout)['result']
    assert report['bootstrap_state'] == 'complete' and report['manifest'] == manifest
    assert (target / 'bundle-manifest.json').read_bytes() == manifest_bytes
    assert all((target / path).read_bytes() == content for path, content in files)
    assert 'bundle-manifest.json' not in {r['path'] for r in manifest['entries']}
    assert {r['path']: r['sha256'] for r in manifest['entries']} == {p: sha256(b).hexdigest() for p, b in files}
    if kind != 'project':
        assert manifest['bundle_kind'] == 'partial' and manifest['read_only'] is True
        assert manifest['scope_descriptor']['scope_kind'] == kind
        before = inventory(target)
        refused = run_cli(['bundle', 'create', '--project', str(target), '--scope', 'project',
                           '--output', str(tmp_path / 'forbidden.zip'), '--format=json'], tmp_path, capture=True)
        assert refused.returncode == 7 and inventory(target) == before
        assert not (tmp_path / 'forbidden.zip').exists()
    else:
        assert manifest['bundle_kind'] == 'project' and manifest['read_only'] is False


@pytest.mark.parametrize('fault', ['payload', 'manifest', 'consistent_replacement', 'document_alias', 'partial_writable'])
def test_public_extraction_rejects_tampering_and_aliases_before_target_creation(archives, tmp_path, fault):
    _, raw, manifest_bytes, files = next(row for row in archives if row[0] == 'document')
    manifest = json.loads(manifest_bytes)
    with ZipFile(BytesIO(raw)) as archive:
        members = {n: archive.read(n) for n in archive.namelist()}
    if fault in ('payload', 'consistent_replacement'):
        selected = next(p for p, _ in files if p.startswith('spec/'))
        members[selected] += b'\n'
        if fault == 'consistent_replacement':
            row = next(r for r in manifest['entries'] if r['path'] == selected)
            row.update(size=len(members[selected]), sha256=sha256(members[selected]).hexdigest())
    elif fault == 'manifest': manifest['entries'][0]['sha256'] = 'f' * 64
    elif fault == 'document_alias': manifest['bundle_kind'] = 'document'
    else: manifest['read_only'] = False
    members['bundle-manifest.json'] = jcs(manifest)
    changed = foreign_zip(sorted(members.items(), key=lambda p: p[0].encode()))
    source = tmp_path / 'changed.zip'; source.write_bytes(changed)
    target = tmp_path / 'must-not-exist'
    args = ['bundle', 'extract', str(source), '--output', str(target), '--format=json']
    if fault == 'consistent_replacement': args += ['--expected-sha256', sha256(raw).hexdigest()]
    before = inventory(tmp_path)
    result = run_cli(args, tmp_path, capture=True)
    assert result.returncode == 3, (result.returncode, result.stdout, result.stderr)
    assert not target.exists() and inventory(tmp_path) == before
