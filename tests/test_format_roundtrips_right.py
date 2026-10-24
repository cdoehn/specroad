"""14.o.R: transported review records cannot assert changed contexts current."""
import pytest

from specroad.exchange import prepare_export
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.model.canonical import canonical_json_bytes
from support.exchange_oracles import assert_records_equal, assert_review_status
from support.format_roundtrips import corpus, decode_native_records, export_model
from support.read_only import no_write_attempts
from support.targets import SCOPE


@pytest.mark.parametrize('fmt', ['ndjson', 'csv'])
@pytest.mark.parametrize('change,status', [('source', 'suspect'), ('target', 'suspect'),
    ('relation', 'suspect'), ('new_identity', 'unreviewed'), ('missing_review', 'unreviewed')])
def test_transport_does_not_make_changed_review_bindings_current(fmt, change, status):
    values, attachments, files = corpus()
    decoded = []
    kinds = sorted({v['artifact_type'] for v in values}) if fmt == 'csv' else ['all']
    with no_write_attempts():
        for kind in kinds:
            native, mapping, profile, options = export_model(values, attachments, files, fmt, kind=kind)
            exported = prepare_export(native, ScopeDescriptor(SCOPE), **options)
            decoded.extend(decode_native_records(exported, mapping, profile, fmt))
    recovered = assert_records_equal(decoded, values)
    source, target = recovered[values[0]['id']], recovered[values[1]['id']]
    original_review = canonical_json_bytes(recovered[values[-1]['id']])
    if change == 'source': source['statement'] += '\nChanged source context.'
    elif change == 'target': target['statement'] += ' Changed target context.'
    elif change == 'relation': source['relations'][0]['rationale'] = 'Changed relation context.'
    elif change == 'new_identity': source['relations'][0]['relation_id'] = 'REL-' + '7'*26
    else: del recovered[values[-1]['id']]
    with no_write_attempts():
        result = assert_review_status(recovered.values(), source['id'], source['relations'][0]['relation_id'], status)
    if change != 'missing_review':
        assert canonical_json_bytes(recovered[values[-1]['id']]) == original_review
    if status == 'unreviewed': assert result.selected_review_id is None
