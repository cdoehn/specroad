"""The same W/R contracts must hold without rebuilding any ChangePlan."""
from contextlib import ExitStack, contextmanager
from unittest.mock import patch
import pytest
from specroad.changes import (bind_plan_authoring, prepare_authoring_request,
    resolve_normative_request, RequestIdConflict)
from specroad.storage.project import ProjectSource
from support.receipts import published, finish
from support.publication import prepared
from support.targets import ACTOR
from test_normative_idempotency import inventory


@contextmanager
def forbidden_planning():
    with ExitStack() as stack:
        for path in ('specroad.changes.target.prepare_change_target',
                     'specroad.changes.lifecycle.prepare_change_lifecycle',
                     'specroad.changes.core.prepare_change_plan'):
            stack.enter_context(patch(path, side_effect=AssertionError('a new plan was attempted')))
        yield


def intent(operations):
    return prepare_authoring_request(command_id='change apply', actor=ACTOR,
        operations=operations, request_id='request-1')


def test_replay_needs_no_plan_id_time_basis_or_current_target_model(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):finish(f,h,j)
    value=intent(p.data['operations']);before=inventory(tmp_path)
    assert not {'plan_sha256','planned_at','base_model_root_sha256'} & set(value.data)
    with forbidden_planning():
        result=resolve_normative_request(ProjectSource(tmp_path),value).data
    assert result['action']=='replay' and result['created_ids']==result['result_object']['created_ids']
    assert inventory(tmp_path)==before


def test_saved_plan_and_preplanning_intent_have_identical_results(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):finish(f,h,j)
    bound=bind_plan_authoring(p); early=intent(p.data['operations'])
    with forbidden_planning():
        first=resolve_normative_request(ProjectSource(tmp_path),bound).data
        second=resolve_normative_request(ProjectSource(tmp_path),early).data
    assert first==second


def test_new_request_observation_does_not_plan_or_write(tmp_path):
    prepared(tmp_path);value=intent([]);before=inventory(tmp_path)
    with forbidden_planning():
        result=resolve_normative_request(ProjectSource(tmp_path),value).data
    assert result['action']=='new_request' and not result['write_authorized']
    assert result['locked_recheck_required'] and inventory(tmp_path)==before


def test_conflict_is_decided_before_attempting_a_new_plan(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):finish(f,h,j)
    with forbidden_planning(), pytest.raises(RequestIdConflict) as error:
        resolve_normative_request(ProjectSource(tmp_path),intent([]))
    assert error.value.exit_code==6
