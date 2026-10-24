"""14.o.R: transported review records cannot assert changed contexts current."""
import pytest

from specroad.exchange import decode_ndjson, prepare_export, select_csv_profile
from specroad.graph.relations import SourceRelations
from specroad.graph.review_status import RelationReviewStatuses
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.mappings import select_mapping
from specroad.model.canonical import canonical_json_bytes
from support.format_roundtrips import corpus, export_model
from support.read_only import no_write_attempts
from support.targets import SCOPE


@pytest.mark.parametrize('fmt', ['ndjson', 'csv'])
@pytest.mark.parametrize('change,status', [('source', 'suspect'), ('target', 'suspect'),
    ('relation', 'suspect'), ('new_identity', 'unreviewed'), ('missing_review', 'unreviewed')])
def test_transport_does_not_make_changed_review_bindings_current(fmt, change, status):
    values, attachments, files = corpus()
    recovered = {}
    kinds = sorted({v['artifact_type'] for v in values}) if fmt == 'csv' else ['all']
    with no_write_attempts():
        for kind in kinds:
            native, mapping, profile, options = export_model(values, attachments, files, fmt, kind=kind)
            exported = prepare_export(native, ScopeDescriptor(SCOPE), **options)
            if fmt == 'ndjson':
                rows = [r['object'] for r in decode_ndjson(exported.output_bytes).objects]
            else:
                codec = select_csv_profile([mapping, profile], key=profile.key, expected_sha256=profile.sha256)
                selected = select_mapping([mapping], key=mapping.key, expected_sha256=mapping.sha256)
                rows = [{**selected.artifact(r['external_type'], r['fields'])['artifact'],
                         'id': r['identity']['value']} for r in codec.decode(exported.output_bytes).records]
            recovered.update({r['id']: r for r in rows})
    assert recovered == {v['id']: v for v in values}
    source, target = recovered[values[0]['id']], recovered[values[1]['id']]
    original_review = canonical_json_bytes(recovered[values[-1]['id']])
    if change == 'source': source['statement'] += '\nChanged source context.'
    elif change == 'target': target['statement'] += ' Changed target context.'
    elif change == 'relation': source['relations'][0]['rationale'] = 'Changed relation context.'
    elif change == 'new_identity': source['relations'][0]['relation_id'] = 'REL-' + '7'*26
    else: del recovered[values[-1]['id']]
    with no_write_attempts():
        statuses = RelationReviewStatuses(tuple(SourceRelations(canonical_json_bytes(v)) for v in recovered.values()))
        result = statuses.for_relation(source['id'], source['relations'][0]['relation_id'])
    assert result.status == status and statuses.approval_granted is False
    if change != 'missing_review':
        assert canonical_json_bytes(recovered[values[-1]['id']]) == original_review
    if status == 'unreviewed': assert result.selected_review_id is None
