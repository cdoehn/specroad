"""Restore source metadata and declared original bindings; no network fetches."""
from hashlib import sha256

import pytest

from specroad.recovery import RestoreError, RestoreServices, prepare_restore_plan
from specroad.security import SafetyViolation
from support.read_only import inventory, no_write_attempts
from support.records import record_value
from support.restore import restore_case


@pytest.mark.parametrize('kind', ['project_bundle', 'baseline'])
@pytest.mark.parametrize('maturity', ['draft', 'proposed', 'in_review', 'rejected', 'retired'])
def test_unapproved_source_metadata_needs_no_invented_content_or_external_observation(tmp_path, kind, maturity):
    source = record_value('source', maturity=maturity, locator='https://example.invalid/source')
    options, originals, _ = restore_case(tmp_path, kind,
        values=[record_value('document'), source])
    before = inventory(tmp_path)
    def forbidden(*_):
        raise AssertionError('Unbound metadata must not fetch or invent source bytes')
    with no_write_attempts():
        plan = prepare_restore_plan(**options, services=RestoreServices(source_content=forbidden))
        without_host = prepare_restore_plan(**options)
    assert plan.source_bytes == without_host.source_bytes
    assert inventory(tmp_path) == before
    source_path = next(path for path in originals if path.startswith('spec/sources/'))
    row = next(row for row in plan.data['target']['entries'] if row['path'] == source_path)
    assert row['sha256'] == sha256(originals[source_path]).hexdigest()


@pytest.mark.parametrize('fault,code', [('io', 5), ('safety', 7)])
def test_source_observation_preserves_native_failure_class_without_writes(tmp_path, fault, code):
    options, _, _ = restore_case(tmp_path, values=[record_value('document'),
        record_value('source', content_sha256=sha256(b'original').hexdigest())])
    def observe(*_):
        if fault == 'io':
            raise OSError('Synthetic unavailable source input')
        raise SafetyViolation('Synthetic forbidden source input')
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError) as failed:
        prepare_restore_plan(**options, services=RestoreServices(source_content=observe))
    assert failed.value.exit_code == code
    assert not failed.value.mutation_possible
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('binding', ['hash', 'excerpt'])
@pytest.mark.parametrize('maturity', ['draft', 'approved'])
@pytest.mark.parametrize('fault', [None, 'missing', 'changed'])
def test_declared_source_content_retains_its_current_native_check(tmp_path, binding, maturity, fault):
    raw = b'Original source text.'
    fields = {'content_sha256': sha256(raw).hexdigest()} if binding == 'hash' else {'excerpt': raw.decode()}
    options, _, _ = restore_case(tmp_path,
        values=[record_value('document'), record_value('source', maturity=maturity, **fields)])
    services = RestoreServices(source_content=None if fault == 'missing' else
        lambda *_: b'Changed source text.' if fault == 'changed' else raw)
    before = inventory(tmp_path)
    with no_write_attempts():
        if fault is None:
            assert prepare_restore_plan(**options, services=services).data['expected_target_root']
        else:
            with pytest.raises(RestoreError) as failed:
                prepare_restore_plan(**options, services=services)
            assert failed.value.exit_code == (6 if binding == 'hash' and fault == 'changed' else 3)
    assert inventory(tmp_path) == before
