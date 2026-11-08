"""Shared source/mode matrix; only immutable original bytes have module scope.

Every test still creates its own mutable sources, checkpoints and transaction.
The synthetic build binding never supplies validation or publication authority.
"""
import pytest

from specroad import _build
from support.merge_preparation import baseline_template
from support.merge_application import templates

SOURCE_KINDS = ('local', 'git', 'baseline', 'bundle')
WORK_WINDOWS = (1, 3, 100000)
WORK_MODES = ('direct', 'resumed', 'portable')
REPRESENTATIONS = ('argv', 'mapping')
PHASE_BOUNDARIES = ('input_integrity', 'inventory', 'comparison', 'metadata',
                    'target_validation', 'finalize', 'completed')

source_kinds = pytest.mark.parametrize('kind', SOURCE_KINDS)
work_windows = pytest.mark.parametrize('window', WORK_WINDOWS)
work_modes = pytest.mark.parametrize('mode', WORK_MODES)
representations = pytest.mark.parametrize('representation', REPRESENTATIONS)
phase_boundaries = pytest.mark.parametrize('phase', PHASE_BOUNDARIES)


@pytest.fixture(scope='module')
def template(tmp_path_factory):
    return baseline_template(tmp_path_factory.mktemp('merge-matrix-template')/'project')


@pytest.fixture(scope='module')
def originals(tmp_path_factory):
    return templates(tmp_path_factory.mktemp('merge-matrix-originals'))


@pytest.fixture
def recorded(monkeypatch):
    monkeypatch.setattr(_build, 'BUILD_METADATA', {'format_version': 1,
        'hash_algorithm': 'specroad-dev-payload-v1', 'build_sha256': '4'*64})
