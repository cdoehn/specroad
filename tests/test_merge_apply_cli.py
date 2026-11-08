"""17.l.R: complete public source/Work/Apply parity with the native writer."""
from support.merge_matrix import originals, recorded, source_kinds, work_modes, representations
from base64 import b64decode, b64encode
from pathlib import Path
import json

import pytest

from specroad.merge.preparation import prepare_merge
from specroad.merge import SourceRequest, SourceSnapshot
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.cli.result_schemas import validate_result_document
from specroad.changes.publication_values import PublicationAuthority
from support.merge_application import templates, case, publication, work, complete
from support.merge_publication import tree
from support.migration_cli import invoke, success
from support.read_only import inventory, no_write_attempts
from test_merge_sources import read_only_sources


@source_kinds
@work_modes
@representations
def test_complete_public_merge_preserves_exact_target_for_all_sources_and_work_modes(recorded, tmp_path, originals, kind, mode, representation):
    data = case(tmp_path/'input', originals, kind)
    target, sources, history, _, _ = data
    preparation = prepare_merge(sources, plan_id=data[3]['--plan-id'], history=history)
    expected = {row['path']: b64decode(row['bytes_base64']) for row in preparation['target_files']}
    assert preparation['changed'] is True and expected
    before = inventory(target)
    document, filename, options, directory = publication(tmp_path, data, mode, representation)
    assert inventory(target) == before
    validate_result_document('merge-plan-command-v1', document)
    operation = document['change_plan']['operations'][0]
    assert operation['inputs']['plan_bytes_base64'] == preparation['plan_bytes_base64']
    assert operation['inputs']['metadata_bytes_base64'] == b64encode(jcs(preparation['metadata'])).decode()
    assert b64decode(operation['inputs']['target_bytes_base64']) == jcs(preparation['target'])
    work_before = inventory(directory) if directory else None
    with read_only_sources():
        dry = success(invoke('merge.apply', {**options, '--dry-run': True}, representation,
                             arguments={'merge_plan': str(filename)}, authorize=False))
    assert dry['mode'] == 'dry_run' and dry['execution'] is None and not dry['project_writes_performed']
    assert inventory(target) == before and not (tmp_path/'backup'/'before.zip').exists()
    result = success(invoke('merge.apply', options, representation, arguments={'merge_plan': str(filename)}))
    validate_result_document('merge-apply-command-v1', result)
    assert result['execution']['current_target_verified'] is True
    assert result['execution']['evidence_currently_rechecked'] is True
    assert result['execution']['write_state'] == 'committed' and not result['execution']['replayed']
    assert result['project_writes_performed'] and not result['write_authorized'] and not result['approval_granted']
    assert SourceSnapshot(SourceRequest(target)).files == expected
    goal = next(json.loads(raw) for path, raw in expected.items() if path.startswith('spec/')
                and json.loads(raw)['artifact_type'] == 'goal')
    assert goal['title'] == 'Synthetic ours title' and goal['statement'] == 'Synthetic theirs statement'
    if directory:
        assert inventory(directory) == work_before


def test_all_adapter_fachresults_and_target_bytes_are_equal(recorded, tmp_path, originals):
    results = []
    for kind in ('local', 'git', 'baseline', 'bundle'):
        target, sources, history, options, _ = case(tmp_path/kind, originals, kind)
        result = prepare_merge(sources, plan_id=options['--plan-id'], history=history)
        assert result['target']['target_validated'] is True
        results.append(result['target_files'])
    assert all(value == results[0] for value in results)


@representations
def test_historical_retry_proves_receipt_before_opening_old_sources_or_backup(recorded, tmp_path, originals, representation):
    data = case(tmp_path/'input', originals)
    _, filename, options, _ = publication(tmp_path, data)
    arguments = {'merge_plan': str(filename)}
    first = success(invoke('merge.apply', options, representation, arguments=arguments))
    target = data[0]
    goal = next(p for p in target.glob('spec/**/*.json') if json.loads(p.read_bytes()).get('artifact_type') == 'goal')
    value = json.loads(goal.read_bytes()); value['title'] = 'Later independent edit'; goal.write_bytes(jcs(value))
    (tmp_path/'backup'/'before.zip').unlink()
    # These live paths need not exist once the old native receipt proves this operation.
    minimal = {key: value for key, value in options.items() if key in ('--project', '--expected-plan-sha256')}
    before = inventory(tmp_path)
    with no_write_attempts():
        replay = success(invoke('merge.apply', minimal, representation, arguments=arguments))
    assert inventory(tmp_path) == before and replay['execution']['replayed']
    assert not replay['project_writes_performed'] and not replay['execution']['current_target_verified']
    assert not replay['execution']['evidence_currently_rechecked']
    assert replay['execution']['receipts'] == first['execution']['receipts']
    refused = invoke('merge.apply', {**options, '--dry-run': True}, representation, arguments=arguments, authorize=False)
    assert refused.exit_code != 0 and inventory(tmp_path) == before


@pytest.mark.parametrize('authority', ['missing', 'deny'])
def test_publication_requires_current_host_authority(recorded, tmp_path, originals, authority):
    data = case(tmp_path/'input', originals)
    _, filename, options, _ = publication(tmp_path, data)
    before = tree(data[0])
    denied = PublicationAuthority('synthetic-negative-host', '1', lambda request: False)
    result = invoke('merge.apply', options, arguments={'merge_plan': str(filename)},
                    authorize=False, authority=denied if authority == 'deny' else None)
    assert result.exit_code in (2, 7), (result.exit_code, result.diagnostics)
    assert tree(data[0]) == before


@pytest.mark.parametrize('failure', ['plan_hash', 'missing_source', 'stale_ours', 'stale_theirs', 'backup', 'wrong_project'])
def test_new_apply_rejects_incomplete_stale_or_wrong_originals(recorded, tmp_path, originals, failure):
    data = case(tmp_path/'input', originals)
    _, filename, options, _ = publication(tmp_path, data)
    if failure == 'plan_hash': options['--expected-plan-sha256'] = '0'*64
    elif failure == 'missing_source': del options['--theirs']
    elif failure in ('stale_ours', 'stale_theirs'):
        root = data[0] if failure == 'stale_ours' else Path(options['--theirs'])
        name = next(p for p in root.glob('spec/**/*.json') if json.loads(p.read_bytes()).get('artifact_type') == 'goal')
        value = json.loads(name.read_bytes()); value['title'] += ' changed'; name.write_bytes(jcs(value))
    elif failure == 'backup': (tmp_path/'backup'/'before.zip').write_bytes(b'not an authorized before image')
    else: options['--project'] = options['--theirs']
    before = inventory(tmp_path)
    result = invoke('merge.apply', options, arguments={'merge_plan': str(filename)})
    assert result.exit_code in (2, 3, 5, 6, 7), (result.exit_code, result.diagnostics)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('option', ['--project', '--actor-type', '--request-id', '--change-plan-id'])
def test_publication_parameters_are_not_silently_ignored_in_passive_mode(recorded, tmp_path, originals, option):
    data = case(tmp_path/'input', originals)
    value = data[4][option]
    before = inventory(tmp_path)
    result = invoke('merge.plan', {**data[3], option: value}, authorize=False)
    assert result.exit_code == 2 and inventory(tmp_path) == before


def test_public_writer_interruption_retains_native_recovery_and_no_automatic_retry(recorded, tmp_path, originals, monkeypatch):
    from specroad.changes import schema_transition as writer
    data = case(tmp_path/'input', originals)
    _, filename, options, _ = publication(tmp_path, data)
    hit = []
    def interrupt(point):
        if point == 'journal:committing:0':
            hit.append(point)
            raise OSError('Synthetic CLI writer durability interruption')
    with monkeypatch.context() as patch:
        patch.setattr(writer, '_checkpoint', interrupt)
        result = invoke('merge.apply', options, arguments={'merge_plan': str(filename)})
    assert hit == ['journal:committing:0'] and result.exit_code == 6
    assert result.details['write_state'] == 'unknown'
    before = inventory(tmp_path)
    retry = invoke('merge.apply', options, arguments={'merge_plan': str(filename)})
    assert retry.exit_code in (3, 5, 6) and inventory(tmp_path) == before
    assert not retry.result


def test_public_same_request_different_operations_is_a_proven_conflict(recorded, tmp_path, originals):
    data = case(tmp_path/'first-input', originals)
    first_root = tmp_path/'first'; first_root.mkdir()
    _, first_file, options, _ = publication(first_root, data)
    other = case(tmp_path/'other-input', originals)
    other_root = tmp_path/'other'; other_root.mkdir()
    second, second_file, _, _ = publication(other_root, other)
    success(invoke('merge.apply', options, arguments={'merge_plan': str(first_file)}))
    before = inventory(tmp_path)
    result = invoke('merge.apply', {'--project': str(data[0]), '--expected-plan-sha256': second['change_plan_sha256']},
                    arguments={'merge_plan': str(second_file)})
    assert result.exit_code == 6, (result.exit_code, result.diagnostics)
    assert inventory(tmp_path) == before
