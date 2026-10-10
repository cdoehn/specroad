"""Real root creation, byte-bound distribution inputs and unchanged foreign files."""
from hashlib import sha256
import json
import os
from pathlib import Path

import pytest

from specroad.authoring import _bootstrap_io as bootstrap
from specroad.changes._lock_files import LockFiles
from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.result_schemas import validate_result_document
from specroad.cli.self_description import describe_command
from specroad.model.configuration import ProjectConfiguration
from specroad.model.identities import artifact_identity
from specroad.profiles.composition import compose_profiles
from specroad.profiles.values import ProfileResource
from specroad.security import ProjectBoundary
from specroad.storage.language_registry import bundled_language_registry, read_language_registry
from specroad.storage.language_packages import bundled_package_index, load_bundled_package
from specroad.storage.operational_preflight import observe_operational_preflight
from specroad.storage.profiles import load_bundled_profile
from specroad.storage.project import ProjectSource
from specroad.storage.record_artifact import read_record_artifact
from support.command_parity import build_core, process_environment, run_python
from support.read_only import inventory, no_write_attempts


EXPECTED_DIRECTORIES = {
    'spec', 'profiles', 'rules', 'mappings', 'attachments', 'archive', 'archive/objects', 'generated',
    'profiles/language-data', 'profiles/language-data/packages', '.specroad', '.specroad/cache',
    '.specroad/locks', '.specroad/tmp', '.specroad/transactions', '.specroad/transactions/receipts',
    '.specroad/requests', '.specroad/merge', '.specroad/recovery',
    *('spec/' + d for d in ('goals', 'needs', 'capabilities', 'requirements', 'scenarios', 'decisions',
        'risks', 'assumptions', 'components', 'interfaces', 'sources', 'verifications', 'tests',
        'evidence', 'releases', 'milestones', 'tasks', 'terms', 'proposals', 'baselines', 'issues',
        'documents', 'sections', 'content-blocks', 'views', 'code-refs', 'relation-reviews', 'configurations')),
}


def check_project(root, result):
    assert result.exit_code == 0
    payload = result.as_dict()['result']
    validate_result_document('project-init-v1', payload)
    source = ProjectSource(root)
    configuration = ProjectConfiguration(json.loads((root / 'specroad.json').read_bytes()))
    assert payload['project_root'] == str(root.resolve())
    assert configuration.project_id == payload['project_id']
    assert configuration.id_prefix == 'SR'
    assert set(payload['directories']) == EXPECTED_DIRECTORIES
    assert all((root / p).is_dir() for p in EXPECTED_DIRECTORIES)
    documents = list((root / 'spec').rglob('*.json'))
    assert len(documents) == 1
    document = read_record_artifact(source, documents[0].relative_to(root).as_posix(), expected_type='document')
    assert document.id == payload['primary_document_id']
    assert document.data['document_role'] == 'primary_specification'
    assert document.data['maturity'] == 'draft' and document.data['revision'] == 1
    assert document.data['relations'] == []
    assert document.data['created_by'] == {'actor_type': 'tool', 'actor_id': 'specroad.init'}
    assert document.data['updated_by'] == document.data['created_by']
    assert document.data['created_at'] == document.data['updated_at']
    assert artifact_identity(document.data).id_scheme == 'random128-v1'
    bound = read_language_registry(source)
    assert bound.source_bytes == bundled_language_registry().source_bytes
    profiles = tuple(ProfileResource((root / 'profiles' / (name + '.json')).read_bytes())
                     for name in ('core', 'software-de', 'software-en'))
    assert all(p.source_bytes == load_bundled_profile(p.key).source_bytes for p in profiles)
    assert configuration.data['profiles'] == ['core@0.2.0', 'software-de@0.2.0']
    compose_profiles(profiles, core_key='core@0.2.0', project_profiles=configuration.data['profiles'][1:])
    packages = bundled_package_index()
    assert len(packages) == 9
    assert configuration.data['language_packages'] == [p['package_id'] + '@' + p['version'] for p in packages]
    for item in packages:
        package = load_bundled_package(item['package_id'] + '@' + item['version'])
        assert (root / 'profiles/language-data/packages' / (item['package_id'] + '.json')).read_bytes() == package.source_bytes
    assert len(payload['files']) == 15
    for item in payload['files']:
        raw = (root / item['path']).read_bytes()
        assert len(raw) == item['size'] and sha256(raw).hexdigest() == item['sha256']
    assert payload['full_semantic_validation'] is False
    assert payload['bootstrap_state'] == 'complete'
    assert not (root / bootstrap.STAGING).exists()
    assert observe_operational_preflight(source.boundary)['consistency_state'] == 'consistent'
    with LockFiles(root) as files:
        assert files.journal_entries() == ()
    return payload


@pytest.mark.parametrize('route', ['cli', 'request', 'registry'])
@pytest.mark.parametrize('kind', ['missing', 'empty', 'repository', 'empty_roots'])
def test_init_creates_real_bound_minimum_project(tmp_path, route, kind):
    target = tmp_path / 'new project'; preserved = {}
    if kind != 'missing': target.mkdir()
    if kind == 'repository':
        (target / '.git').mkdir(); (target / '.git/config').write_bytes(b'owned repository metadata\n')
        (target / 'README.md').write_bytes(b'foreign content\n')
        for p in (target / '.git/config', target / 'README.md'):
            preserved[p] = (p.read_bytes(), p.stat().st_ino, p.stat().st_mode)
    roots = {}
    if kind == 'empty_roots':
        for name in ('spec', 'profiles', 'rules', 'mappings', 'attachments', 'archive', 'generated', '.specroad'):
            p = target / name; p.mkdir(); roots[name] = p.stat().st_ino
    if route == 'cli': result = dispatch_result(['init', target.name, '--format=json'], cwd=tmp_path)
    elif route == 'request':
        result = execute_request({'command_id': 'init', 'arguments': {'path': target.name}}, cwd=tmp_path).result
    else:
        registry = builtin_registry()
        result = registry.execute_result(registry.parse(['init', str(target)]), cwd=tmp_path)
    check_project(target, result)
    assert all((p.read_bytes(), p.stat().st_ino, p.stat().st_mode) == state for p, state in preserved.items())
    assert all((target / name).stat().st_ino == value for name, value in roots.items())
    if kind != 'repository': assert not (target / '.git').exists()


@pytest.mark.parametrize('route', ['cli', 'request'])
def test_omitted_path_uses_current_invocation_directory(tmp_path, route):
    target = tmp_path / 'selected'; target.mkdir()
    result = (dispatch_result(['init'], cwd=target) if route == 'cli'
              else execute_request({'command_id': 'init'}, cwd=target).result)
    check_project(target, result)
    assert not (tmp_path / 'specroad.json').exists()


@pytest.mark.parametrize('name', ['specroad.json', 'spec', 'profiles', '.specroad', 'generated'])
@pytest.mark.parametrize('kind', ['file', 'symlink'])
def test_existing_claimed_path_is_rejected_before_writes(tmp_path, name, kind):
    root = tmp_path / 'repository'; root.mkdir()
    foreign = tmp_path / 'foreign'; foreign.write_bytes(b'preserve me')
    if kind == 'file': (root / name).write_bytes(b'original normative or foreign data')
    else: (root / name).symlink_to(foreign)
    before = inventory(tmp_path)
    with no_write_attempts(): result = dispatch_result(['init', str(root)])
    assert result.exit_code == (7 if kind == 'symlink' else 6)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('name', ['spec', 'profiles', '.specroad', 'SPEC', '.specroad-bootstrap'])
def test_nonempty_or_reserved_namespace_remains_untouched(tmp_path, name):
    root = tmp_path / 'repository'; root.mkdir()
    folder = root / name; folder.mkdir(); (folder / 'foreign').write_bytes(b'not ours')
    before = inventory(tmp_path)
    with no_write_attempts(): result = dispatch_result(['init', str(root)])
    assert result.exit_code == 6
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('after', [False, True])
@pytest.mark.parametrize('existing', [False, True])
def test_ordinary_publication_failure_rolls_back_only_owned_paths(tmp_path, monkeypatch, after, existing):
    target = tmp_path / 'project'
    if existing:
        target.mkdir(); (target / 'foreign').write_bytes(b'keep exactly')
    before = inventory(tmp_path); original = bootstrap.rename_new; failed = False
    def fail_once(function, source_fd, source, target_fd, destination):
        nonlocal failed
        if destination == 'profiles' and not failed:
            failed = True
            if after: original(function, source_fd, source, target_fd, destination)
            raise OSError('owned injected publication failure')
        return original(function, source_fd, source, target_fd, destination)
    monkeypatch.setattr(bootstrap, 'rename_new', fail_once)
    result = dispatch_result(['init', str(target)])
    assert failed and result.exit_code == 5
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('after', [False, True])
def test_preparation_failure_leaves_no_partial_project(tmp_path, monkeypatch, after):
    target = tmp_path / 'project'; before = inventory(tmp_path); original = bootstrap.BootstrapTree.write
    def fail_once(self, path, raw):
        if path == 'specroad.json':
            if after: original(self, path, raw)
            raise OSError('owned injected preparation failure')
        return original(self, path, raw)
    monkeypatch.setattr(bootstrap.BootstrapTree, 'write', fail_once)
    assert dispatch_result(['init', str(target)]).exit_code == 5
    assert inventory(tmp_path) == before


def test_configuration_is_last_and_every_move_has_a_durable_journal(tmp_path, monkeypatch):
    target = tmp_path / 'project'; target.mkdir()
    original = bootstrap.rename_new; destinations = []
    def observe(function, source_fd, source, target_fd, destination):
        journal = json.loads((target / bootstrap.STAGING / 'journal.json').read_bytes())
        assert journal['state'] == 'prepared'
        assert journal['root_identity'] == [target.stat().st_dev, target.stat().st_ino]
        assert not (target / 'specroad.json').exists()
        assert source in journal['units']
        destinations.append(destination)
        return original(function, source_fd, source, target_fd, destination)
    monkeypatch.setattr(bootstrap, 'rename_new', observe)
    check_project(target, dispatch_result(['init', str(target)]))
    assert destinations[-1] == 'specroad.json' and len(destinations) == 9


@pytest.mark.parametrize('name', ['tmp', 'merge'])
def test_new_operational_directories_are_only_clear_while_empty(tmp_path, name):
    target = tmp_path / 'project'
    check_project(target, dispatch_result(['init', str(target)]))
    path = '.specroad/' + name + '/foreign'; (target / path).write_bytes(b'preserve pending data')
    before = inventory(target)
    with no_write_attempts():
        observation = observe_operational_preflight(ProjectBoundary(target))
        with LockFiles(target) as files: active = files.journal_entries()
    assert observation['consistency_state'] == 'unknown' and observation['unknown_paths'] == [path]
    assert active == ('.specroad/' + name,)
    assert inventory(target) == before


def test_current_native_root_mutex_blocks_concurrent_creation(tmp_path):
    root = tmp_path / 'project'; root.mkdir(); before = inventory(tmp_path)
    with LockFiles(root) as held:
        held.acquire()
        result = dispatch_result(['init', str(root)])
    assert result.exit_code == 5
    assert inventory(tmp_path) == before


def test_independent_initializations_allocate_new_random_identities(tmp_path):
    a = check_project(tmp_path / 'a', dispatch_result(['init', str(tmp_path / 'a')]))
    b = check_project(tmp_path / 'b', dispatch_result(['init', str(tmp_path / 'b')]))
    assert a['project_id'] != b['project_id'] and a['primary_document_id'] != b['primary_document_id']


def test_description_reports_root_creation_without_creating_it(tmp_path):
    before = inventory(tmp_path)
    with no_write_attempts():
        described = dispatch_result(['command', 'describe', 'init'], cwd=tmp_path)
    assert described.exit_code == 0 and inventory(tmp_path) == before
    contract = describe_command(builtin_registry(), 'init')
    assert contract['command_class'] == contract['preflight_profile'] == 'root_creation'
    assert contract['write_effects']['scope'] == 'new_root'
    assert contract['lock_kind'] == 'bootstrap' and contract['requires_project'] is False
    assert contract['requires_git'] is False and contract['stdin']['mode'] == 'unused'
    assert set(contract['exit_codes']) == {0, 2, 3, 4, 5, 6, 7}


@pytest.mark.parametrize('distribution', ['module', 'zipapp'])
def test_built_distribution_initializes_without_project_imports_or_path(tmp_path, distribution):
    repository = Path(__file__).resolve().parents[1]; output = tmp_path / 'build'
    built = build_core(repository, output)
    assert built.returncode == 0, built.stderr
    target = tmp_path / 'new project'
    (tmp_path / 'sitecustomize.py').write_text("raise AssertionError('project code executed')\n")
    if distribution == 'module':
        body = 'import sys;sys.path.insert(0,sys.argv.pop(1));from specroad.__main__ import main;raise SystemExit(main())'
        arguments = [str(output / 'module'), 'init', str(target), '--format=json']
    else:
        body = 'import runpy,sys;sys.argv=[sys.argv[1],*sys.argv[2:]];runpy.run_path(sys.argv[0],run_name="__main__")'
        arguments = [str(output / 'specroad.pyz'), 'init', str(target), '--format=json']
    result = run_python(body, arguments, cwd=tmp_path, environment=process_environment())
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data['command'] == 'init' and data['status'] == 'success'
    assert data['summary']['complete'] is True
    source = ProjectSource(target)
    assert source.configuration.project_id == data['result']['project_id']
    assert len(list((target / 'spec/documents').glob('*.json'))) == 1
    assert not (target / bootstrap.STAGING).exists()
