"""Native journal, publication, receipts and recovery for byte-only changes."""
from hashlib import sha256
import os
from unittest.mock import patch
import pytest
from specroad.changes import (CommittingJournal, PublicationAuthority, PublicationCheckError,
    CommitPublicationError, begin_building_journal, publish_prepared_journal,
    finalize_committing_journal, cleanup_completed_transaction, project_lock,
    TransactionReceipt, complete_published_transaction, rollback_interrupted_transaction)
from support.normalization import prepared, staged
from support.folds import goal
from support.publication import options, files, ALLOW, TRANSACTION
from support.recovery import RECOVER
from support.read_only import inventory


def recovery_options(journal):
    return dict(kind='recovery', command='recover run', project_id='sample',
                request_id=journal.data['request_id'], transaction_id=TRANSACTION)


def test_native_writer_normalizes_only_selected_artifact_and_finalizes_real_receipts(tmp_path):
    first, second = goal(1), goal(2)
    path = 'spec/goals/' + first['id'] + '.json'
    with staged(tmp_path, artifacts=[first, second], paths=[path]) as (m, p, c, held, ready):
        expected = {**m.source_files, **{d.path: d.content for d in c.request.documents}}
        assert ready.data['base_model_root_sha256'] == ready.data['target_model_root_sha256']
        assert [f['path'] for f in ready.data['files']] == [path]
        for row in ready.data['files']:
            assert (tmp_path / row['before_image_path']).read_bytes() == m.source_files[path]
        result = publish_prepared_journal(c, ready, held_lock=held, authority=ALLOW)
        assert result.data['published_count'] == 1 and files(tmp_path) == expected
        journal = CommittingJournal((tmp_path / ready.path).read_bytes())
        done = finalize_committing_journal(c, journal, held_lock=held, authority=ALLOW)
        assert done.data['commit_completed'] and done.data['current_target_verified']
        receipt = TransactionReceipt((tmp_path / done.data['receipts']['transaction']['path']).read_bytes())
        assert receipt.data['operations'] == p.data['operations']
        assert receipt.data['result_object']['published_paths'] == [path]
        cleanup_completed_transaction(c, TRANSACTION, held_lock=held, authority=ALLOW)
        assert files(tmp_path) == expected and not (tmp_path / ready.path).exists()
    for document in c.request.documents:
        import json
        assert json.loads(document.content) == first
        assert sha256(document.content).hexdigest() == p.data['operations'][0]['target_byte_sha256']


@pytest.mark.parametrize('changed_index', [0, 1])
def test_stale_selected_or_untouched_bytes_refuse_before_journal_creation(tmp_path, changed_index):
    m, p, c = prepared(tmp_path, artifacts=[goal(1), goal(2)],
        paths=['spec/goals/' + goal(1)['id'] + '.json'])
    path = tmp_path / m.documents[changed_index].path
    path.write_bytes(b' ' + path.read_bytes())
    before = files(tmp_path)
    with project_lock(tmp_path, **options(c)) as held:
        with pytest.raises(PublicationCheckError):
            begin_building_journal(c, held_lock=held, transaction_id=TRANSACTION, authority=ALLOW)
    assert files(tmp_path) == before and not (tmp_path / '.specroad/transactions').exists()


def test_denied_authority_does_not_publish_or_create_a_journal(tmp_path):
    m, _, c = prepared(tmp_path)
    deny = PublicationAuthority('deny', '1', lambda request: False)
    with project_lock(tmp_path, **options(c)) as held:
        before = inventory(tmp_path)
        with pytest.raises(PublicationCheckError) as error:
            begin_building_journal(c, held_lock=held, transaction_id=TRANSACTION, authority=deny)
        assert error.value.exit_code == 7 and inventory(tmp_path) == before
    assert files(tmp_path) == m.source_files


def test_changed_staging_bytes_cannot_be_published_even_with_equal_semantic_values(tmp_path):
    with staged(tmp_path) as (m, _, c, held, ready):
        path = tmp_path / ready.data['files'][0]['staging_path']
        path.write_bytes(path.read_bytes() + b' ')
        with pytest.raises(CommitPublicationError):
            publish_prepared_journal(c, ready, held_lock=held, authority=ALLOW)
        assert files(tmp_path) == m.source_files


def test_recovery_completes_exact_normalized_target_despite_equal_model_roots(tmp_path):
    with staged(tmp_path) as (m, p, c, held, ready):
        publish_prepared_journal(c, ready, held_lock=held, authority=ALLOW)
        journal = CommittingJournal((tmp_path / ready.path).read_bytes())
        target = files(tmp_path)
    assert target != m.source_files
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        done = complete_published_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
            expected_journal_sha256=journal.sha256)
        assert done.data['commit_completed'] and done.data['normative_writes'] == 0
    assert files(tmp_path) == target
    receipt = TransactionReceipt((tmp_path / done.data['receipts']['transaction']['path']).read_bytes())
    assert receipt.data['operations'] == p.data['operations']


def test_partial_normalization_rolls_back_to_exact_original_bytes(tmp_path):
    with staged(tmp_path, artifacts=[goal(1), goal(2)]) as (m, _, c, held, ready):
        replace = os.replace
        published = []
        def stop(src, dst, **kwargs):
            if dst != 'journal.json' and published:
                raise OSError(5, 'interrupted before second artifact')
            result = replace(src, dst, **kwargs)
            if dst != 'journal.json': published.append(dst)
            return result
        with patch.object(os, 'replace', side_effect=stop):
            with pytest.raises(CommitPublicationError):
                publish_prepared_journal(c, ready, held_lock=held, authority=ALLOW)
        journal = CommittingJournal((tmp_path / ready.path).read_bytes())
    assert journal.data['published_count'] == 1 and files(tmp_path) != m.source_files
    with project_lock(tmp_path, **recovery_options(journal)) as held:
        result = rollback_interrupted_transaction(TRANSACTION, held_lock=held, authority=RECOVER,
            expected_journal_sha256=journal.sha256)
        assert result.data['rollback_completed']
    assert files(tmp_path) == m.source_files
