"""Real file-prefix crashes, explicit native recovery and shared request history."""
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import pytest
from tests.support.migration_transaction import setup, apply, normative, journal_path
from tests.support.migration_plans import ACTOR, planned_files
from specroad.changes.schema_transition_values import SchemaTransitionError, TransitionJournal
from specroad.changes.locking import project_lock
from specroad.changes.recovery_values import RecoveryAuthority
from specroad.changes.recovery import (discard_unpublished_transaction,
    rollback_interrupted_transaction, complete_published_transaction, inspect_recovery)
from specroad.changes.receipt_values import transaction_receipt_path, request_receipt_path
from specroad.storage.operational_preflight import observe_operational_preflight
from specroad.security import ProjectBoundary
from specroad.model.errors import ModelError
from specroad.changes.execution_values import ChangeExecutionError
from specroad.security import SafetyViolation

FAILURES=(ModelError,ChangeExecutionError,SafetyViolation,OSError)


def tree(root):
    return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}













# This literal synthetic fixture has thirteen native file effects. Collection
# only declares cases; planning/backups and all I/O run inside each Apply test.
FILE_CHANGE_INDICES = tuple(range(13))
FILE_CRASH_CASES = tuple((kind, index) for kind in ('effect', 'ack')
                        for index in FILE_CHANGE_INDICES)






def test_original_request_replays_historical_result_after_later_edit(tmp_path):
    root,source,plan,args=setup(tmp_path);first=apply(root,plan,args)
    path=root/'spec/requirements/SR-REQ-0001.json';value=json.loads(path.read_bytes())
    value['revision']+=1;value['title']='Later ordinary project edit'
    path.write_text(json.dumps(value));before=tree(root)
    # Replay needs durable original proof, not a still-existing external ZIP.
    Path(args['backup_path']).unlink()
    replay=apply(root,plan,args)
    assert replay['replayed'] and not replay['current_target_verified']
    for name in ('published_paths','target_model_root_sha256','transaction_id','request_id'):
        assert replay[name]==first[name]
    assert tree(root)==before
    from specroad.changes.receipt_read import read_transaction_completion
    from specroad.storage.project import ProjectSource
    observation=read_transaction_completion(ProjectSource(root),args['transaction_id']).data
    assert observation['receipt_verified'] and not observation['current_target_verified']


def test_new_request_at_target_is_noop_without_revision_or_receipt(tmp_path):
    a=tmp_path/'a';a.mkdir();root,source,plan,args=setup(a);apply(root,plan,args)
    b=tmp_path/'b';b.mkdir();_,_,other,options=setup(b,fields={'request_id':'synthetic:second'})
    before=tree(root);result=apply(root,other,options)
    assert result['status']=='not_required' and result['no_change']
    assert result['write_state']=='not_committed' and not result['current_target_verified']
    assert tree(root)==before


def test_request_conflict_uses_shared_normative_namespace(tmp_path):
    a=tmp_path/'a';a.mkdir();root,source,plan,args=setup(a);apply(root,plan,args)
    b=tmp_path/'b';b.mkdir();_,_,other,options=setup(b,fields={'planned_at':'2026-11-04T03:00:00Z'})
    before=tree(root)
    with pytest.raises(FAILURES) as seen:apply(root,other,options)
    assert seen.value.reason=='request_operations_conflict'
    assert tree(root)==before
    from specroad.changes.receipt_read import _read_confirmed_request
    from specroad.storage.project import ProjectSource
    receipt=_read_confirmed_request(ProjectSource(root),plan.data['request_id'])
    assert receipt.data['operations_sha256']
    assert receipt.data['format_version']=='request-receipt-v2'
