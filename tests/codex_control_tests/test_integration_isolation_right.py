"""The test-only external root does not relax real path or cleanup boundaries."""
from pathlib import Path

import pytest

from codex_control_tests import external_temp
from specroad_control.errors import ControlError
from specroad_control.local import outside


def test_git_and_symlink_candidates_are_rejected_without_writes(monkeypatch):
    with external_temp.temporary_directory(prefix='cg-') as raw:
        root = Path(raw)
        repository = root / 'repo'
        repository.mkdir()
        (repository / '.git').mkdir()
        link = root / 'linked'
        link.symlink_to(root, target_is_directory=True)
        before = sorted(str(p.relative_to(root)) for p in root.rglob('*'))
        monkeypatch.setattr(external_temp, 'TEMP_PARENTS', (repository, link))
        with pytest.raises(RuntimeError, match='outside Git'):
            external_temp.temporary_directory()
        assert sorted(str(p.relative_to(root)) for p in root.rglob('*')) == before
        with pytest.raises(ControlError, match='Git working tree'):
            outside(repository / 'state')


def test_rejected_candidate_falls_back_to_an_independent_private_root(monkeypatch):
    with external_temp.temporary_directory(prefix='cf-') as raw:
        root = Path(raw)
        repository = root / 'repo'
        repository.mkdir()
        (repository / '.git').mkdir()
        monkeypatch.setattr(external_temp, 'TEMP_PARENTS', (repository, root))
        with external_temp.temporary_directory(prefix='a-') as first:
            with external_temp.temporary_directory(prefix='b-') as second:
                assert first != second
                assert Path(first).parent == Path(second).parent == root
                assert outside(Path(first)) == Path(first)
                assert outside(Path(second)) == Path(second)
            assert not Path(second).exists()
            assert Path(first).is_dir()
        assert not Path(first).exists()
        assert list(repository.iterdir()) == [repository / '.git']


def test_unusable_socket_length_removes_its_owned_temporary_directory(monkeypatch):
    with external_temp.temporary_directory(prefix='cl-') as raw:
        root = Path(raw)
        monkeypatch.setattr(external_temp, 'TEMP_PARENTS', (root,))
        with pytest.raises(RuntimeError, match='short private test directory'):
            external_temp.temporary_directory(socket_suffix='s' * 108)
        assert list(root.iterdir()) == []
