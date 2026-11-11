from dataclasses import replace
from unittest.mock import patch
from uuid import uuid4
import pytest
from specroad_control.config import Config
from specroad_control.exchange import Exchange
from specroad_control.errors import ControlError
from codex_control_tests.automation_support import FakeCore, package


def setup_exchange(root):
    binding = dict(repo_id=str(uuid4()), base_commit='a'*40, state_fingerprint='b'*16,
                   fingerprint_algorithm='patchharbor-state-v1')
    config = Config(root/'dev', root, str(uuid4()), repo_id=binding['repo_id'])
    return Exchange(config, FakeCore()), binding


def test_archive_move_reuses_only_exact_verified_content(tmp_path):
    exchange, binding = setup_exchange(tmp_path)
    original=package(tmp_path/'one.zip',dict(kind='patch',binding=binding))
    first=list(exchange.candidates('patch',lambda m: True))
    archive=tmp_path/'PatchHarbor-Archive';archive.mkdir();(tmp_path/'one.zip').rename(archive/'renamed.zip')
    with patch.object(exchange.core,'patch',wraps=exchange.core.patch) as calls:
        second=list(exchange.candidates('patch',lambda m: True))
    assert calls.call_count==0 and first[0]['sha256']==second[0]['sha256']
    assert second[0]['path']==str(archive/'renamed.zip')


def test_replaced_bytes_and_late_followup_are_not_hidden_by_cache(tmp_path):
    exchange,binding=setup_exchange(tmp_path)
    package(tmp_path/'one.zip',dict(kind='patch',binding=binding))
    original=list(exchange.candidates('patch',lambda m: True))[0]
    package(tmp_path/'one.zip',dict(kind='patch',binding=binding,changed=True))
    package(tmp_path/'two.zip',dict(kind='patch',binding=binding,another=True))
    with patch.object(exchange.core,'patch',wraps=exchange.core.patch) as calls:
        current=list(exchange.candidates('patch',lambda m: True))
    assert len(current)==2 and calls.call_count==2
    assert original['sha256'] not in {r['sha256'] for r in current}


def test_native_rejection_is_never_cached_as_success(tmp_path):
    exchange,binding=setup_exchange(tmp_path)
    package(tmp_path/'bad.zip',dict(kind='patch',binding=binding,reject=True))
    assert list(exchange.candidates('patch',lambda m: True))==[]
    package(tmp_path/'bad.zip',dict(kind='patch',binding=binding))
    assert len(list(exchange.candidates('patch',lambda m: True)))==1


def test_deleted_or_symlinked_artifact_is_not_served_from_cache(tmp_path):
    exchange,binding=setup_exchange(tmp_path)
    package(tmp_path/'one.zip',dict(kind='patch',binding=binding))
    assert len(list(exchange.candidates('patch',lambda m: True)))==1
    (tmp_path/'one.zip').unlink();(tmp_path/'one.zip').symlink_to(tmp_path/'missing')
    assert list(exchange.candidates('patch',lambda m: True))==[]
