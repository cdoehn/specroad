"""Real compressed-plan admission above the previous bound and at 64 MiB."""
import pytest
from specroad_control.apply_reconcile_proof import plan
from specroad_control.errors import ControlError
from codex_control_tests.plan_size_support import sized_package, BINDING


def test_default_admits_over_32_mib_and_exactly_64_mib_with_verified_payloads(tmp_path):
    for size in (32*1024*1024+1, 64*1024*1024):
        fact, expected = sized_package(tmp_path/'bounded.zip',size)
        actual, program_sha = plan(fact)
        assert actual['binding'] == BINDING
        assert actual['stages'][0]['after'] == expected
        assert actual['handoff_kind'] == 'patch_ready' and len(program_sha) == 64
        del actual


def test_one_byte_above_64_mib_is_rejected_despite_small_compressed_zip(tmp_path):
    path = tmp_path/'oversized.zip'
    fact, _ = sized_package(path,64*1024*1024+1)
    assert path.stat().st_size < 1024*1024
    with pytest.raises(ControlError,match='Incomplete or oversized compressed plan'):
        plan(fact)
