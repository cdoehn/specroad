"""20.h.W: actual CPython 3.10..3.14, built Core and native offline transport."""
from hashlib import sha256
import json
from pathlib import Path

import pytest
from build_core import build_core
from language_packaging.runtime_matrix import load_runtime_matrix
from specroad.authoring._inspection_snapshot import InspectionSnapshot
from support.portable import files_under
from support.payload_identity import reference_payload, reference_digest
from support.transport_outbound import child, ROOT, tree
from support.transport_return import origin, sandbox, offline_export
from support.transport_receive import receive
from support.records import ref
from specroad.storage import _relation_cache
from support.domain import domain_value
from test_proposal_basis import project as validation_project
from support.python_matrix import MINORS, runtime_prefix, fresh_cli, runtime_evidence, REVIEW_PROGRAM


@pytest.fixture(scope='module')
def matrix_runtimes():
    # Actual operator-selected binaries, not simulated sys.version_info values.
    # Absent/mismatched runtimes fail the gate; never silently skip a matrix row.
    return load_runtime_matrix()['interpreters']


@pytest.fixture(scope='module')
def matrix_distribution(tmp_path_factory):
    return build_core(ROOT / 'src', tmp_path_factory.mktemp('python-matrix') / 'portable')


@pytest.mark.parametrize('minor', MINORS)
@pytest.mark.parametrize('route', ('module', 'pyz'))
def test_real_minor_runs_built_entrypoints_without_installation(tmp_path, matrix_distribution, matrix_runtimes, minor, route, record_property):
    row = matrix_runtimes[minor]; source = matrix_distribution[route == 'pyz']
    before = files_under(matrix_distribution[0].parent)
    # Every invocation starts in a new, untrusted unrelated working directory.
    arguments = (['version', '--format=json'], ['capabilities', '--format=json'],
                 ['command', 'describe', 'query', '--format=json'], ['--help'])
    for index, args in enumerate(arguments):
        cwd = tmp_path / str(index); cwd.mkdir()
        for name in ('specroad.py', 'sitecustomize.py', 'json.py'):
            (cwd / name).write_text('raise AssertionError("untrusted cwd code loaded")\n')
        protected = files_under(cwd)
        result = fresh_cli(row, minor, source, cwd, args)
        assert result.returncode == 0, (args, result.stdout, result.stderr)
        assert files_under(cwd) == protected
        if index == 0:
            version = json.loads(result.stdout)['result']
            assert version['runtime']['python_version'] == row['version']
            assert version['distribution_kind'] == ('zipapp' if route == 'pyz' else 'module')
            expected = reference_digest(reference_payload(ROOT / 'src/specroad',
                (matrix_distribution[0] / '__main__.py').read_bytes()))
            assert version['build_sha256'] == expected
            assert version['python_support']['declared_minors'] == list(MINORS)
            assert version['python_support']['minimum_minor'] == '3.10'
            assert version['python_support']['fully_verified_minors'] == []
            assert version['python_support']['tested_minors'] == []
            assert version['supported_output_format_versions']['json']
    assert files_under(matrix_distribution[0].parent) == before
    evidence = runtime_evidence(row, minor, source, tmp_path)
    assert evidence['runtime']['build_sha256'] == expected
    assert evidence['isolation']['nonprivileged'] and evidence['uid'] != 0
    assert evidence['site_enabled'] is False
    record_property('python_matrix', json.dumps(evidence, sort_keys=True))


@pytest.mark.parametrize('minor', MINORS)
@pytest.mark.parametrize('route', ('module', 'pyz'))
def test_real_minor_completes_native_offline_roundtrip_and_separate_host_review(tmp_path, matrix_distribution, matrix_runtimes, minor, route, record_property):
    row = matrix_runtimes[minor]; python = row['executable']
    source = matrix_distribution[route == 'pyz']
    host = tmp_path / 'host'; host.mkdir()
    handoff = origin(host, matrix_distribution, python=python)
    protected_host = tree(handoff['repository'])
    remote = tmp_path / 'remote'; remote.mkdir()
    value, proposal = sandbox(remote, matrix_distribution, handoff, source=source, python=python)
    project = remote / 'sandbox/project'
    # Prepare an empty optional cache parent before witnessing the reader input.
    # No cached result, source change or replacement validator is supplied.
    (project / _relation_cache.CACHE_PATH).parent.mkdir(parents=True, exist_ok=True)
    protected = files_under(project)
    # A native goal-only project needs no unavailable document/configuration
    # services. Keep an actual successful, complete validation in every row.
    validation_root = remote / 'validation-project'
    validation_project(validation_root, bundled=True, artifacts=[domain_value('goal')])
    validation_before = files_under(validation_root)
    cwd = remote / 'validate-complete'; cwd.mkdir()
    answer = fresh_cli(row, minor, source, cwd,
                       ['validate', '--project', str(validation_root), '--format=json'])
    assert answer.returncode == 0, answer.stdout.decode(errors='replace') + answer.stderr.decode(errors='replace')
    complete = json.loads(answer.stdout)
    assert complete['summary']['complete'] is True
    assert complete['result']['status'] == 'success' and complete['result']['checks_complete'] is True
    assert complete['result']['source_report']['identified_ids'] == [ref('GOAL')]
    assert not complete['result']['approval_granted'] and not complete['result']['write_authorized']
    assert files_under(validation_root) == validation_before
    # The transported document/configuration require semantic gates that this
    # public reader does not supply. Exact refusal is not complete validation.
    cwd = remote / 'validate-unavailable'; cwd.mkdir()
    answer = fresh_cli(row, minor, source, cwd,
                       ['validate', '--project', str(project), '--format=json'])
    assert answer.returncode == 5, answer.stdout.decode(errors='replace') + answer.stderr.decode(errors='replace')
    unavailable = json.loads(answer.stdout)
    assert unavailable['summary']['complete'] is False
    assessment = unavailable['result']
    assert assessment['status'] == 'failed' and assessment['checks_complete'] is False
    assert not assessment['approval_granted'] and not assessment['write_authorized']
    stages = {stage['stage']: stage for stage in assessment['source_report']['stages']}
    assert {name for name, stage in stages.items() if stage['status'] == 'unavailable'} == {'document_model', 'configuration'}
    for name, identity in (('document_model', ref('DOC')), ('configuration', ref('CFG'))):
        assert stages[name]['checked_ids'] == [identity]
        assert stages[name]['diagnostics'] == [{'reason': 'validation_required_gate_unavailable',
                                               'severity': 'error', 'gate_id': name}]
    assert {d['code'] for d in unavailable['diagnostics']} == {'VALIDATION_UNAVAILABLE'}
    assert files_under(project) == protected
    # Query and rendering remain successful fresh public CLI calls; only
    # structured results and file effects are oracles, never rendered text.
    for index, args in enumerate((['query', '--limit', '100'], ['render', ref('DOC')])):
        cwd = remote / ('call-' + str(index)); cwd.mkdir()
        answer = fresh_cli(row, minor, source, cwd, [*args, '--project', str(project), '--format=json'])
        assert answer.returncode == 0, (args, answer.stdout, answer.stderr)
        outcome = json.loads(answer.stdout)
        assert outcome['summary']['complete'] is True
        assert files_under(project) == protected
    result = offline_export(remote, source, value, python=python)
    assert result['code'] == 0, result
    returned = result['outcome']['result']
    package = Path(returned['file']['path'])
    assert sha256(package.read_bytes()).hexdigest() == returned['file']['sha256']
    assert not returned['approval_granted'] and not returned['write_authorized']
    assert files_under(project) == protected and tree(handoff['repository']) == protected_host
    original = InspectionSnapshot(handoff['origin'], None).model.source_files
    received = receive(handoff, package, source, python=python)
    assert received['status'] == 'proposal_received' and received['patchharbor']['success'], received
    assert received['patchharbor']['result_status'] == 'created'
    assert not received['applied'] and not received['approval_granted']
    now = InspectionSnapshot(handoff['origin'], None).model.source_files
    assert {k:v for k,v in now.items() if k != proposal.original.path} == original
    imported = json.loads(now[proposal.original.path])
    assert imported['proposal_status'] == imported['maturity'] == 'draft'
    assert imported['reviews'] == imported['control_history'] == []
    target = proposal.data['change_plan']['expected_result']['model_root_sha256']
    program = ('import json\nfrom pathlib import Path\nsys.path.append(' + repr(str(ROOT / 'tests')) + ')\n'
        + 'root=Path(' + repr(str(handoff['origin'])) + ')\n'
        + 'proposal_path=' + repr(proposal.original.path) + '\nexpected_target=' + repr(target) + '\n'
        + REVIEW_PROGRAM)
    reviewed = child(host, program, source=source, python=python)
    assert reviewed == {'runtime': row['version'], 'target_sha256': target,
                        'dry_run_preserved_bytes': True, 'proposal_status': 'applied'}
    evidence = runtime_evidence(row, minor, source, remote)
    evidence['sandbox_return_sha256'] = returned['file']['sha256']
    evidence['validation'] = {'goal_complete': complete['result']['checks_complete'],
        'roundtrip_complete': assessment['checks_complete'],
        'unavailable_gates': sorted(name for name, stage in stages.items() if stage['status'] == 'unavailable')}
    evidence['host'] = {'git_and_entrypoint_required': True, 'synthetic_review': True, **reviewed}
    record_property('python_matrix_roundtrip', json.dumps(evidence, sort_keys=True))
