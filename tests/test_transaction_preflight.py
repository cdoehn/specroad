"""A recovered old transaction never starts or consumes the requested new change."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from specroad.changes import (RecoveryAuthority, RecoveryError, transaction_preflight,
                              project_lock, transaction_receipt_path, request_receipt_path)
from specroad.cli.contracts import CommandClass
from specroad.storage.read_only import diagnose_read_only, validate_project_read_only
from support.automatic_recovery import pending, writer
from support.model import configuration_file
from support.publication import TRANSACTION, files
from support.read_only import inventory, no_write_attempts, profile_resources
from support.targets import ACTOR

ALLOW = RecoveryAuthority('automatic-test-host', '1', lambda request: True)
NEW_REQUEST = 'next-unstarted-request'


def automatic(root, **overrides):
    options = dict(command_class=CommandClass.NORMATIVE_WRITE,
        request_id=NEW_REQUEST, expected_project_id='sample', authority=ALLOW, actor=ACTOR)
    return transaction_preflight(root, **{**options, **overrides})


@pytest.mark.parametrize('state', ['building', 'prepared', 'partial', 'complete', 'committed'])
def test_automatic_recovery_finishes_old_work_and_requires_new_invocation(tmp_path, state):
    source, change, expected = pending(tmp_path, state)
    journal_path = tmp_path / '.specroad/transactions' / TRANSACTION / 'journal.json'
    original_journal = journal_path.read_bytes()
    original_work = {p.relative_to(journal_path.parent).as_posix(): p.read_bytes()
                     for p in journal_path.parent.rglob('*') if p.is_file() and p != journal_path}
    result = automatic(tmp_path).data
    assert result['exit_code'] == 5 and result['reason'] == 'recovery_completed_reinvoke', result
    assert result['recovery_attempted'] and result['recovery_completed']
    assert result['requires_new_invocation'] and not result['transaction_preflight_passed']
    assert not result['normal_operation_started'] and not result['model_loaded']
    assert result['request_id'] == NEW_REQUEST and not result['request_consumed']
    assert not result['write_authorized'] and not result['recovery_required']
    assert result['mutation_possible']
    assert files(tmp_path) == expected
    assert not journal_path.exists()
    assert not (tmp_path / request_receipt_path(NEW_REQUEST)).exists()
    receipt = json.loads((tmp_path / transaction_receipt_path(TRANSACTION)).read_bytes())
    assert receipt['outcome'] == ('committed' if state in ('complete', 'committed') else 'rolled_back')
    archived = {p.relative_to(tmp_path).as_posix(): p.read_bytes() for p in
                (tmp_path / '.specroad/recovery/transaction-audit').rglob('*') if p.is_file()}
    for suffix, raw in original_work.items():
        assert any(path.endswith('/' + suffix) and content == raw for path, content in archived.items())
    if state in ('building', 'prepared', 'committed'):
        assert original_journal in archived.values()
    before = inventory(tmp_path)
    with no_write_attempts():
        again = automatic(tmp_path).data
        profile, = profile_resources()
        reader = validate_project_read_only(tmp_path, profile_resources=[profile], core_key=profile.key)
    assert inventory(tmp_path) == before
    assert again['exit_code'] == 0 and again['transaction_preflight_passed']
    assert not again['normal_operation_started'] and not again['recovery_attempted']
    assert reader.exit_code == 0 and reader.data['model_loaded']
    with project_lock(tmp_path, kind='writer', command='change apply', project_id='sample',
                      request_id=NEW_REQUEST, transaction_id='next-transaction'):
        pass


READ_CALLS = [(CommandClass.READ_ONLY, False), (CommandClass.PLAN_OUTPUT, False),
              (CommandClass.GENERATED_OUTPUT, False), (CommandClass.NORMATIVE_WRITE, True)]


@pytest.mark.parametrize('command_class,dry_run', READ_CALLS)
@pytest.mark.parametrize('state', ['prepared', 'partial', 'complete'])
def test_read_plan_generated_and_dry_run_remain_write_free(tmp_path, state, command_class, dry_run):
    pending(tmp_path, state)
    before = inventory(tmp_path)
    calls = []
    authority = RecoveryAuthority('must-not-run', '1', lambda request: calls.append(request))
    with no_write_attempts():
        result = transaction_preflight(tmp_path, command_class=command_class, dry_run=dry_run,
            request_id=NEW_REQUEST, authority=authority, actor=ACTOR).data
    assert inventory(tmp_path) == before and calls == []
    assert result['exit_code'] == 5 and result['recovery_required']
    assert not result['normal_operation_started'] and not result['model_loaded']
    assert not result['mutation_possible'] and not result['recovery_attempted']
    assert result['operational']['journal_contents_loaded'] is False


@pytest.mark.parametrize('policy', [False, None])
def test_missing_or_disabled_auto_policy_has_no_operational_effect(tmp_path, policy):
    pending(tmp_path, auto_recover=policy)
    before = inventory(tmp_path)
    with no_write_attempts():
        result = automatic(tmp_path).data
    assert result['exit_code'] == 5 and result['reason'] == 'automatic_recovery_disabled'
    assert inventory(tmp_path) == before and not result['mutation_possible']


@pytest.mark.parametrize('decision', [False, 1, None])
def test_denied_or_nonboolean_authority_never_acquires_a_recovery_lock(tmp_path, decision):
    pending(tmp_path)
    before = inventory(tmp_path)
    authority = RecoveryAuthority('denied', '1', lambda request: decision)
    with no_write_attempts():
        result = automatic(tmp_path, authority=authority).data
    assert result['exit_code'] == 7
    assert inventory(tmp_path) == before and not result['recovery_attempted']


def test_live_writer_is_not_automatically_taken_over(tmp_path):
    with writer(tmp_path):
        before = inventory(tmp_path)
        with no_write_attempts():
            result = automatic(tmp_path).data
        assert result['exit_code'] == 5 and result['owner_state'] == 'alive'
        assert inventory(tmp_path) == before and not result['recovery_attempted']


def test_short_metadata_budget_precedes_authorized_owner_diagnosis(tmp_path, monkeypatch):
    with writer(tmp_path):
        config = tmp_path / 'specroad.json'
        raw = config.read_bytes()
        raw += b' ' * (1024 * 1024 - 256 - len(raw))
        config.write_bytes(raw)
        before = inventory(tmp_path)
        reads, authorized = [], []
        native = os.read

        def observed(fd, size):
            value = native(fd, size)
            reads.append((os.readlink('/proc/self/fd/' + str(fd)), len(value)))
            return value

        def authorize(request):
            authorized.append((sum(size for path, size in reads), tuple(reads)))
            return True

        monkeypatch.setattr(os, 'read', observed)
        with no_write_attempts():
            result = automatic(tmp_path, authority=RecoveryAuthority('budget-host', '1', authorize)).data
        assert len(authorized) == 1
        assert len(raw) <= authorized[0][0] <= 1024 * 1024
        assert all(path == str(config) for path, size in authorized[0][1])
        assert result['metadata_bytes_read'] <= 1024 * 1024
        assert result['exit_code'] == 5 and result['owner_state'] == 'alive'
        assert not result['recovery_attempted'] and inventory(tmp_path) == before


@pytest.mark.parametrize('state', ['prepared', 'partial', 'complete'])
def test_real_dead_writer_uses_audited_takeover_without_new_request(tmp_path, state):
    root = Path(__file__).resolve().parents[1]
    code = '''import sys, os, json
from hashlib import sha256
from pathlib import Path
sys.path[:0] = [str(Path(sys.argv[1])/p) for p in ('src','tests')]
from support.automatic_recovery import writer
with writer(Path(sys.argv[2]), sys.argv[3]) as (model, plan, expected):
    print(json.dumps({p:sha256(b).hexdigest() for p,b in expected.items()}), flush=True)
    os._exit(23)
'''
    child = subprocess.run([sys.executable, '-I', '-B', '-c', code, str(root), str(tmp_path), state],
                           capture_output=True, text=True, check=False)
    assert child.returncode == 23, child.stderr
    expected = json.loads(child.stdout)
    result = automatic(tmp_path).data
    assert result['exit_code'] == 5 and result['recovery_completed'], result
    assert {p: sha256(b).hexdigest() for p, b in files(tmp_path).items()} == expected
    assert not (tmp_path / request_receipt_path(NEW_REQUEST)).exists()
    intent, = (tmp_path / '.specroad/recovery/transaction-audit').glob('*/takeover-*/intent.json')
    assert json.loads(intent.read_bytes())['observed_owner_state'] == 'dead'


def test_more_than_sixteen_active_entries_block_without_full_scan_or_journal_read(tmp_path, monkeypatch):
    configuration_file(tmp_path)
    transactions = tmp_path / '.specroad/transactions'
    transactions.mkdir(parents=True)
    for n in range(40):
        (transactions / ('txn-' + str(n))).mkdir()
    before = inventory(tmp_path)
    scanned = []
    native = os.stat

    def observed(path, *args, **kwargs):
        if isinstance(path, str) and path.startswith('txn-'):
            scanned.append(path)
        return native(path, *args, **kwargs)

    monkeypatch.setattr(os, 'stat', observed)
    with no_write_attempts():
        result = transaction_preflight(tmp_path, command_class=CommandClass.READ_ONLY).data
    assert result['exit_code'] == 5 and result['recovery_required']
    assert len(result['operational']['unresolved_paths']) == 16
    assert not result['operational']['inspection_complete']
    assert len(scanned) == 32  # Two independent bounded observations, sixteen each.
    assert inventory(tmp_path) == before


def test_broken_model_and_configuration_do_not_prevent_metadata_diagnosis(tmp_path):
    pending(tmp_path)
    (tmp_path / 'specroad.json').write_bytes(b'{broken configuration')
    journal = tmp_path / '.specroad/transactions' / TRANSACTION / 'journal.json'
    journal.write_bytes(b'broken journal')
    before = inventory(tmp_path)
    with no_write_attempts():
        result = transaction_preflight(tmp_path, command_class=CommandClass.READ_ONLY).data
        diagnostic = diagnose_read_only(tmp_path).data
        profile, = profile_resources()
        reader = validate_project_read_only(tmp_path, profile_resources=[profile], core_key=profile.key)
    assert result['exit_code'] == reader.exit_code == 5
    assert result['recovery_required'] and not result['model_loaded']
    assert diagnostic['exit_code'] == 0 and not diagnostic['model_loaded']
    assert inventory(tmp_path) == before


def test_clean_gate_does_not_read_artifact_or_receipt_history(tmp_path):
    configuration_file(tmp_path)
    passive = tmp_path / '.specroad/transactions/receipts'
    passive.mkdir(parents=True)
    (passive / 'broken.json').write_bytes(b'not a current transaction')
    before = inventory(tmp_path)
    with no_write_attempts():
        result = transaction_preflight(tmp_path, command_class=CommandClass.READ_ONLY)
    assert result.exit_code == 0 and result.data['transaction_preflight_passed']
    assert not result.data['model_loaded'] and not result.data['write_authorized']
    assert inventory(tmp_path) == before
    with pytest.raises(TypeError):
        bool(result)
    detached = result.data
    detached['exit_code'] = 99
    assert result.exit_code == 0


def test_authorization_cannot_change_policy_then_recover_under_the_old_setting(tmp_path):
    pending(tmp_path)
    journal = tmp_path / '.specroad/transactions' / TRANSACTION / 'journal.json'
    original = journal.read_bytes()

    def changed(request):
        config = json.loads((tmp_path / 'specroad.json').read_bytes())
        config['transaction_policy']['auto_recover'] = False
        (tmp_path / 'specroad.json').write_text(json.dumps(config))
        return True

    result = automatic(tmp_path, authority=RecoveryAuthority('changed', '1', changed)).data
    assert result['exit_code'] == 6 and result['reason'] == 'preflight_configuration_changed'
    assert not result['recovery_attempted'] and journal.read_bytes() == original


@pytest.mark.parametrize('command_class', ['normative_write', None, CommandClass.RECOVERY_WRITE,
                                         CommandClass.ROOT_CREATION])
def test_unknown_or_nonnormal_class_is_rejected_before_project_io(tmp_path, command_class):
    with no_write_attempts(), pytest.raises(RecoveryError) as error:
        transaction_preflight(tmp_path / 'absent', command_class=command_class)
    assert error.value.exit_code == 2
