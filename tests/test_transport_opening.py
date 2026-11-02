"""15.o.W: real offline handoffs, complete inner validation and native receipts."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
from zipfile import ZipFile

import pytest
from build_core import build_core

from specroad.cli.application import dispatch_result
from specroad.cli.commands import builtin_registry
from specroad.cli.requests import CommandRequest
from specroad.cli.result_schemas import validate_result_document
from specroad.model.errors import ModelError
from specroad.storage.project import ProjectSource
from support.read_only import no_write_attempts
from support.transport_outbound import ROOT, tree
from support.transport_opening import make_handoff, opening_request, offline
from test_bundle_receipts import receipts, retry


@pytest.fixture(scope='module')
def distribution(tmp_path_factory):
    return build_core(ROOT / 'src', tmp_path_factory.mktemp('opening-distribution') / 'build')


@pytest.fixture(scope='module', params=(False, True), ids=('repository-root', 'subproject'))
def handoff(tmp_path_factory, distribution, request):
    return make_handoff(tmp_path_factory.mktemp('native-handoff'), distribution, subproject=request.param)


@pytest.mark.parametrize('route', ('module', 'pyz'))
@pytest.mark.parametrize('expected', (False, True))
def test_complete_verify_offline_keeps_inputs_and_separates_private_output(tmp_path, distribution, handoff, route, expected):
    value = opening_request(tmp_path, handoff, expected=expected)
    before = tree(handoff['source'].parent), tree(handoff['origin'])
    result = offline(tmp_path, distribution[route == 'pyz'], value)
    assert result['code'] == 0, result
    data = result['outcome']['result']
    validate_result_document('ai-runtime-verify-v1', data)
    assert data['external_hash_verified'] is expected
    assert data['manifest']['model_root_sha256'] == handoff['expected'].manifest['bundle_model_root_sha256']
    assert data['manifest']['project_id'] == handoff['expected'].manifest['project_id']
    assert data['file']['sha256'] == sha256(handoff['source'].read_bytes()).hexdigest()
    assert all(data[k] is True for k in ('full_reference_valid', 'runtime_binding_verified', 'closure_verified'))
    assert all(data[k] is False for k in ('creator_authenticated', 'approval_granted', 'write_authorized'))
    assert (tree(handoff['source'].parent), tree(handoff['origin'])) == before
    assert {p.name for p in tmp_path.iterdir()} == {'verification'}
    assert (tmp_path / 'verification').stat().st_mode & 0o777 == 0o700
    assert (tmp_path / 'verification/result.zip').stat().st_mode & 0o777 == 0o600
    for path in (tmp_path / 'verification/code').rglob('*'):
        assert not path.stat().st_mode & 0o077


@pytest.mark.parametrize('route', ('module', 'pyz'))
@pytest.mark.parametrize('empty', (False, True))
@pytest.mark.parametrize('entry', ('argv', 'structured'))
def test_extract_publishes_exact_originals_and_native_project(tmp_path, distribution, handoff, route, empty, entry):
    request = opening_request(tmp_path, handoff, extract=True, expected=False)
    target = tmp_path / 'sandbox'
    if empty:
        target.mkdir(mode=0o750)
    result = offline(tmp_path, distribution[route == 'pyz'], request, argv=entry == 'argv')
    assert result['code'] == 0, result
    data = result['outcome']['result']; validate_result_document('ai-runtime-extract-v1', data)
    assert data['project_root'] == str(target / 'project')
    assert ProjectSource(target / 'project').configuration.project_id == handoff['expected'].manifest['project_id']
    assert (target / 'reference/outbound.zip').read_bytes() == handoff['source'].read_bytes()
    with ZipFile(handoff['source']) as archive:
        assert (target / 'reference/result.zip').read_bytes() == archive.read('reference/result.zip')
        assert (target / 'runtime/specroad.pyz').read_bytes() == archive.read('runtime/specroad.pyz')
    assert (target / 'runtime/patchharbor-1.8.0.pyz').read_bytes() == handoff['runtime'].read_bytes()
    for name, raw in handoff['expected'].files.items():
        assert (target / 'project' / name).read_bytes() == raw
    assert (target / 'project/bundle-manifest.json').read_bytes() == handoff['expected'].manifest_bytes
    assert (target / '.specroad/recovery/sandbox-bootstrap/journal.json').is_file()
    assert (target / 'project/.specroad/recovery/bundle-bootstrap/journal.json').is_file()
    assert not (target / '.specroad-bootstrap').exists()
    assert {p['path'] for p in data['files']} == {
        'runtime/specroad.pyz', 'runtime/patchharbor-1.8.0.pyz', 'reference/outbound.zip', 'reference/result.zip',
        'project/bundle-manifest.json', *('project/' + p for p in handoff['expected'].files)}
    for row in data['files']:
        raw = (target / row['path']).read_bytes()
        assert row['size'] == len(raw) and row['sha256'] == sha256(raw).hexdigest()


def test_receipts_keep_native_historical_replay_after_project_move(tmp_path, distribution):
    package_root = tmp_path / 'fixture'; package_root.mkdir()
    handoff = make_handoff(package_root, distribution, history=True)
    sandbox = tmp_path / 'offline'; sandbox.mkdir()
    value = opening_request(sandbox, handoff, extract=True)
    result = offline(sandbox, distribution[1], value)
    assert result['code'] == 0, result
    target = sandbox / 'sandbox/project'
    before = tree(target)
    with no_write_attempts():
        outcome = retry(target, handoff['selected'])
    assert outcome['action'] == 'replay' and outcome['normative_writes'] == 0
    assert outcome['write_authorized'] is False
    assert receipts(target) == receipts(handoff['origin']) and tree(target) == before
    moved = tmp_path / 'moved'; (sandbox / 'sandbox').rename(moved)
    with no_write_attempts():
        assert retry(moved / 'project', handoff['selected']) == outcome
    # A fresh process derives references only from the preserved original files.
    again = tmp_path / 'second-offline'; again.mkdir()
    package = {'source': moved / 'reference/outbound.zip', 'runtime': moved / 'runtime/patchharbor-1.8.0.pyz'}
    checked = offline(again, moved / 'runtime/specroad.pyz', opening_request(again, package))
    assert checked['code'] == 0 and checked['outcome']['result']['manifest'] == result['outcome']['result']['manifest']


@pytest.mark.parametrize('command,kind', (('bundle.verify', 'read_only'), ('bundle.extract', 'root_creation')))
def test_metadata_binds_variant_effects_without_loading_runtime(command, kind):
    with no_write_attempts():
        registry = builtin_registry()
        described = dispatch_result(['command', 'describe', command])
        assert described.exit_code == 0
        variant, = described.as_dict()['result']['variants']
        invocation = registry.bind_request(CommandRequest.from_mapping(variant['example']))
    assert invocation.command.command_class.value == kind
    assert not invocation.command.requires_project and not invocation.command.requires_git
    assert variant['when'] == {'--profile': ['ai-runtime']}
    assert 'runtime_workspace' in variant['required_write_paths']
    assert 'explicit_external_private_workspace' in variant['operating_effects']
    assert variant['result_schema'] == 'ai-runtime-' + command.split('.')[1] + '-v1'
    # W.4.1 preserves the ordinary command's budget contract (N.2/O).
    expected_budget = {'bundle.verify': 'runtime-budget-v2', 'bundle.extract': None}[command]
    assert variant['budget_policy_version'] == expected_budget
    assert invocation.command.budget_policy_version == expected_budget
    assert described.as_dict()['result']['budget_policy_version'] == expected_budget
    document = described.as_dict()['result']
    with no_write_attempts():
        validate_result_document('command-description-v1', document)
        # Budgeted Verify and nullable Extract variants remain closed and typed;
        # adding its declared fields must not admit arbitrary machine claims.
        for field, value in (('result_schema', ''), ('result_schema', False),
                ('required_write_paths', 'runtime_workspace'), ('required_write_paths', [False]),
                ('budget_policy_version', False), ('undeclared_authority', True)):
            invalid = deepcopy(document)
            invalid['variants'][0][field] = value
            with pytest.raises(ModelError):
                validate_result_document('command-description-v1', invalid)
        for field in ('result_schema', 'required_write_paths', 'budget_policy_version'):
            invalid = deepcopy(document)
            del invalid['variants'][0][field]
            with pytest.raises(ModelError):
                validate_result_document('command-description-v1', invalid)


@pytest.mark.parametrize('change', ('missing-runtime', 'missing-digest', 'missing-workspace', 'bad-hash',
    'extra-profile', 'no-profile', 'relative-workspace', 'direction', 'return-reference', 'work', 'relative-input'))
def test_invalid_requests_cannot_create_operating_paths(tmp_path, distribution, handoff, change):
    value = opening_request(tmp_path, handoff)
    options = value['options']
    if change == 'missing-runtime': del options['--patchharbor-pyz']
    elif change == 'missing-digest': del options['--patchharbor-pyz-sha256']
    elif change == 'missing-workspace': del options['--runtime-workspace']
    elif change == 'bad-hash': options['--expected-sha256'] = 'short'
    elif change == 'extra-profile': options['--profile'].append('core')
    elif change == 'no-profile': del options['--profile']
    elif change == 'relative-workspace': options['--runtime-workspace'] = 'scratch'
    elif change == 'direction': options['--direction'] = 'outbound'
    elif change == 'return-reference': options['--reference'] = str(handoff['source'])
    elif change == 'work': options['--work-dir'] = str(tmp_path / 'work')
    elif change == 'relative-input': value['arguments']['file'] = 'relative.zip'
    result = offline(tmp_path, distribution[0], value)
    assert result['code'] == 2, result
    assert list(tmp_path.iterdir()) == []


def test_untrusted_cwd_cannot_supply_runtime_modules(tmp_path, distribution, handoff):
    sentinel = tmp_path / 'untrusted-code-executed'
    for name in ('patchharbor.py', 'sitecustomize.py'):
        (tmp_path / name).write_text('from pathlib import Path\nPath(' + repr(str(sentinel)) + ').touch()\n')
    result = offline(tmp_path, distribution[1], opening_request(tmp_path, handoff, extract=True))
    assert result['code'] == 0, result
    assert not sentinel.exists()
