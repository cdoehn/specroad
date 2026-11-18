"""18.q.W: real native return packages in module/PYZ Python-only sandboxes."""
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from build_core import build_core

from specroad.cli.application import dispatch_result
from specroad.cli.commands import builtin_registry
from specroad.cli.requests import CommandRequest
from specroad.cli.result_schemas import validate_result_document
from specroad.model.canonical import canonical_json_bytes
from support.transport_outbound import ROOT, tree
from support.transport_return import origin, sandbox, offline_export


@pytest.fixture(scope='module')
def distribution(tmp_path_factory):
    return build_core(ROOT / 'src', tmp_path_factory.mktemp('return-core') / 'build')


@pytest.fixture(scope='module', params=(False, True), ids=('repository-root', 'subproject'))
def handoff(tmp_path_factory, distribution, request):
    return origin(tmp_path_factory.mktemp('return-origin'), distribution, subproject=request.param)


@pytest.mark.parametrize('route', ('module', 'pyz'))
@pytest.mark.parametrize('argv', (False, True))
def test_native_return_is_one_bound_passive_patch_without_input_writes(tmp_path, distribution, handoff, route, argv):
    value, proposal = sandbox(tmp_path, distribution, handoff)
    before = tree(tmp_path / 'sandbox'), tree(handoff['repository']), proposal.source_bytes
    answer = offline_export(tmp_path, distribution[route == 'pyz'], value, argv=argv)
    assert answer['code'] == 0, answer
    result = answer['outcome']['result']; validate_result_document('proposal-return-export-v1', result)
    assert result['status'] == 'created' and result['generated']
    assert not result['normative'] and not result['approval_granted'] and not result['write_authorized']
    path = Path(result['file']['path']); raw = path.read_bytes()
    assert result['file']['sha256'] == sha256(raw).hexdigest()
    assert list((tmp_path / 'output').glob('*.zip')) == [path]
    manifest = result['manifest']; key = '.specroad-return/' + manifest['return_id']
    without_id = {k:v for k,v in manifest.items() if k != 'return_id'}
    assert manifest['return_id'] == sha256(b'specroad-proposal-return-v1\0' + canonical_json_bytes(without_id)).hexdigest()
    with ZipFile(path) as archive:
        native = json.loads(archive.read('patch.json'))
        for field in ('repo_id','base_commit','fingerprint_algorithm','state_fingerprint'):
            assert native[field] == manifest['reference'][field]
        environment = json.loads(archive.read('PATCHHARBOR_META/environment.json'))
        assert environment['repository_context'] == {field: native[field] for field in
            ('repo_id', 'base_commit', 'fingerprint_algorithm', 'state_fingerprint')}
        assert native['repo_id'] == handoff['registered']['repo_id']
        assert native['base_commit'] == handoff['registered']['base_commit']
        assert archive.read(key + '/proposal.json') == proposal.source_bytes
        assert archive.read(key + '/return.json') == canonical_json_bytes(manifest)
        entry = archive.read(key + '/receive.sh')
        assert sha256(entry).hexdigest() == manifest['entrypoint_sha256']
        assert b'proposal_received' in entry and b'git ' not in entry and b'pytest' not in entry
        assert set(archive.namelist()) == {'patch.json', 'PATCHHARBOR_META/environment.json',
            'PATCHHARBOR_META/CHAT_INSTRUCTIONS.md', key+'/return.json',key+'/proposal.json',key+'/receive.sh',
            *(key+'/data/'+d['after_sha256'] for d in manifest['delta'] if d['after_sha256'] is not None)}
        for row in manifest['delta']:
            target = archive.read(key + '/data/' + row['after_sha256'])
            assert len(target) == row['size'] and sha256(target).hexdigest() == row['after_sha256']
            assert sha256((handoff['origin']/row['path']).read_bytes()).hexdigest() == row['before_sha256']
            assert json.loads(target)['statement'] == 'Native proposed change'
    assert manifest['proposal']['binding'] == proposal.binding.data
    assert manifest['project_path'] == ('model' if handoff['origin'] != handoff['repository'] else '.')
    assert (tree(tmp_path/'sandbox'),tree(handoff['repository']), (tmp_path/'proposal.json').read_bytes()) == before


def test_no_changes_returns_no_patch_file(tmp_path, distribution, handoff):
    value, _ = sandbox(tmp_path, distribution, handoff, empty=True)
    result = offline_export(tmp_path, distribution[1], value)
    assert result['code'] == 0, result
    data = result['outcome']['result']
    assert data['status'] == 'no_changes' and not data['generated'] and data['file'] is None
    assert list((tmp_path/'output').glob('*.zip')) == []


def test_return_metadata_binds_generated_output_without_git_or_host_authority():
    result = dispatch_result(['command','describe','bundle.create'])
    assert result.exit_code == 0, result.as_dict()
    variants = result.as_dict()['result']['variants']
    variant = next(v for v in variants if v['when'].get('--direction') == 'return')
    command = builtin_registry().bind_request(CommandRequest.from_mapping(variant['example'])).command
    assert command.command_class.value == 'generated_output' and not command.requires_git
    assert command.protocol.result_schema == 'proposal-return-export-v1'
    assert not command.protocol.work.continuation_supported
