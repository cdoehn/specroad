"""Native Force plans and receipts retain the exact public request identity."""
import json

import pytest

from specroad.authoring.native_generic import author_generic
from specroad.changes.request_ids import NormativeRequestId
from support.force_cases import ACTOR, ALLOW, files, fixture


@pytest.mark.parametrize('representation', ['text', 'typed', 'absent'])
def test_native_force_request_identity_survives_dry_run_publication_and_replay(tmp_path, representation):
    root, path = fixture(tmp_path / 'project')
    original = json.loads((root / path).read_bytes())
    identity = None if representation == 'absent' else 'Force.Request:Exact-814'
    supplied = NormativeRequestId(identity) if representation == 'typed' else identity
    intent = dict(command_id='artifact.update', target=original['id'],
        expected_revision=original['revision'],
        patch=[dict(op='replace', path='/title', value='Explicit request identity')])
    before = files(root)
    dry = author_generic(root, intent, actor=ACTOR, request_id=supplied,
        force=True, dry_run=True)
    assert dry['audit']['plan']['request_id'] == identity
    assert files(root) == before

    result = author_generic(root, intent, actor=ACTOR, request_id=supplied,
        force=True, authority=ALLOW)
    plan = result['audit']['plan']
    assert plan['request_id'] == identity
    assert json.loads(json.dumps(plan)) == plan
    assert result['completion']['commit_completed']
    assert result['write_state'] == 'committed' and result['approval_granted'] is False
    assert json.loads((root / path).read_bytes())['title'] == 'Explicit request identity'
    if identity is not None:
        after = files(root)
        alternate = identity if representation == 'typed' else NormativeRequestId(identity)
        replay = author_generic(root, intent, actor=ACTOR, request_id=alternate,
            force=True, authority=ALLOW)
        assert replay['replayed'] and replay['plan_sha256'] == result['plan_sha256']
        assert replay['completion']['current_target_verified'] is False
        assert files(root) == after
