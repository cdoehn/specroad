"""Complete observed project relations, never display/formatting assertions."""
from dataclasses import FrozenInstanceError
import tempfile
from pathlib import Path
import unittest

from specroad.graph.indices import RelationIndex
from specroad.graph.references import RelationReferences
from specroad.graph.relation_views import RelationViews
from specroad.graph.relations import SourceRelations
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.storage.project import ProjectSource
from specroad.storage.relation_index import build_project_relation_index, read_project_relation_views
from support.artifacts import artifact_bytes
from support.model import configuration_file, put
from support.relations import aid, artifact, edge, rid
from support.portable import files_under


def index_of(*values):
    return RelationIndex(RelationReferences(tuple(SourceRelations(artifact_bytes(v)) for v in values)))


def save(root, value):
    return put(root, artifact_path(value['artifact_type'], value['id'], 'SR'), artifact_bytes(value))


class RelationIndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); configuration_file(self.root)

    def pair(self, kind='refines'):
        a = artifact(number=1, relations=[edge(kind, aid(number=2))]); b = artifact(number=2)
        save(self.root, a); save(self.root, b)
        return a, b, ProjectSource(self.root)

    def test_selectively_returned_target_includes_unselected_source(self):
        a, b, source = self.pair()
        result = read_project_relation_views(source, b['id'], direction='incoming')
        self.assertEqual(result.artifact.identity.id, b['id'])
        self.assertEqual(tuple(v.target.id for v in result.views), (a['id'],))
        self.assertEqual(result.source_count, 2); self.assertEqual(result.relation_count, 1)

    def test_pure_index_matches_scan_for_both_directions(self):
        a = artifact(number=1, relations=[edge(target=aid(number=2))]); b = artifact(number=2)
        index = index_of(a, b); scan = RelationViews(index.references)
        for name in (a['id'], b['id']):
            for direction in ('incoming', 'outgoing', 'both'):
                self.assertEqual(index.for_artifact(name, direction=direction), scan.for_artifact(name, direction=direction))

    def test_pure_input_index_does_not_claim_project_completeness(self):
        self.assertEqual(index_of(artifact()).validation_scope, 'supplied_relation_set_only')

    def test_edge_id_and_stored_source_are_preserved_in_inverse(self):
        a, b, source = self.pair()
        result = read_project_relation_views(source, b['id'])
        view = result.views[0]
        self.assertTrue(view.inverse); self.assertFalse(view.normative)
        self.assertEqual(view.relation_id, rid()); self.assertEqual(view.stored.source.id, a['id'])

    def test_superseded_by_remains_computed(self):
        a, b, source = self.pair('supersedes')
        result = read_project_relation_views(source, b['id'])
        self.assertEqual(result.views[0].type, 'superseded_by')
        self.assertEqual(result.views[0].stored.relation.type, 'supersedes')

    def test_symmetric_edges_visible_without_duplicate_normative_copy(self):
        a, b, source = self.pair('conflicts_with')
        left = read_project_relation_views(source, a['id']); right = read_project_relation_views(source, b['id'])
        self.assertEqual(left.relation_count, 1); self.assertEqual(right.relation_count, 1)
        self.assertEqual(left.views[0].relation_id, right.views[0].relation_id)

    def test_known_isolated_artifact_has_empty_incoming_set(self):
        a = artifact(); save(self.root, a)
        self.assertEqual(read_project_relation_views(ProjectSource(self.root), a['id']).views, ())

    def test_empty_project_index_is_valid_but_unknown_lookup_is_not(self):
        source = ProjectSource(self.root); index = build_project_relation_index(source)
        self.assertEqual(index.source_count, 0); self.assertEqual(index.relation_count, 0)
        with self.assertRaises(ModelError): read_project_relation_views(source, aid())

    def test_query_ids_are_not_display_labels(self):
        value = artifact(display_id='shown'); save(self.root, value)
        with self.assertRaises(ModelError): read_project_relation_views(ProjectSource(self.root), 'shown')

    def test_unknown_direction_is_not_silently_both(self):
        a, b, source = self.pair()
        for direction in ('reverse', '', None, 3):
            with self.subTest(direction=repr(direction)), self.assertRaises(ModelError):
                read_project_relation_views(source, a['id'], direction=direction)

    def test_source_files_and_configuration_are_unchanged(self):
        a, b, source = self.pair(); before = files_under(self.root)
        read_project_relation_views(source, b['id']); build_project_relation_index(source)
        self.assertEqual(files_under(self.root), before)

    def test_build_creates_no_cache_or_transaction_directory(self):
        self.pair(); build_project_relation_index(ProjectSource(self.root))
        self.assertFalse((self.root / '.specroad').exists())

    def test_profile_payload_not_interpreted_as_relation_source(self):
        a, b, source = self.pair()
        put(self.root, 'profiles/passive.json', b'{"relations": "not an artifact"}')
        self.assertEqual(read_project_relation_views(source, b['id']).source_count, 2)

    def test_unreferenced_attachments_and_archive_not_sources(self):
        a, b, source = self.pair()
        put(self.root, 'attachments/outside.json', artifact_bytes(artifact(number=3, relations=[edge(number=8)])))
        put(self.root, 'archive/objects/aa/' + 'a' * 64, b'not json')
        self.assertEqual(read_project_relation_views(source, b['id']).relation_count, 1)

    def test_broken_unselected_source_is_an_error_not_partial_success(self):
        a, b, source = self.pair(); put(self.root, artifact_path('requirement', aid(number=9), 'SR'), b'broken')
        with self.assertRaises(ModelError): read_project_relation_views(source, b['id'])

    def test_missing_endpoint_is_an_error(self):
        value = artifact(relations=[edge(target=aid(number=9))]); save(self.root, value)
        with self.assertRaises(ModelError) as caught: read_project_relation_views(ProjectSource(self.root), value['id'])
        self.assertEqual(caught.exception.reason, 'missing_relation_target')

    def test_noncanonical_symmetric_storage_is_not_silently_repaired(self):
        save(self.root, artifact(number=1)); save(self.root, artifact(number=2, relations=[edge('conflicts_with', aid(number=1))]))
        before = files_under(self.root)
        with self.assertRaises(ModelError): build_project_relation_index(ProjectSource(self.root))
        self.assertEqual(files_under(self.root), before)

    def test_enumeration_order_does_not_change_views(self):
        values = [artifact(number=1, relations=[edge(target=aid(number=3), number=5)]),
                  artifact(number=2, relations=[edge(target=aid(number=3), number=4)]), artifact(number=3)]
        self.assertEqual(index_of(*values).for_artifact(aid(number=3)), index_of(*reversed(values)).for_artifact(aid(number=3)))

    def test_outgoing_incoming_and_both_do_not_truncate(self):
        a = artifact(number=2, relations=[edge(target=aid(number=3), number=2)])
        for value in (artifact(number=1, relations=[edge(target=a['id'])]), a, artifact(number=3)): save(self.root, value)
        source = ProjectSource(self.root)
        self.assertEqual(len(read_project_relation_views(source, a['id'], direction='incoming').views), 1)
        self.assertEqual(len(read_project_relation_views(source, a['id'], direction='outgoing').views), 1)
        self.assertEqual(len(read_project_relation_views(source, a['id']).views), 2)

    def test_no_atomic_snapshot_or_approval_is_claimed(self):
        a, b, source = self.pair(); result = read_project_relation_views(source, b['id'])
        self.assertFalse(result.atomic_snapshot)
        self.assertEqual(result.coverage_scope, 'current_project_artifacts')
        self.assertEqual(result.validation_scope, 'relation_references_and_canonical_storage_only')

    def test_result_mutation_cannot_change_source_records(self):
        a, b, source = self.pair(); result = read_project_relation_views(source, b['id'])
        result.artifact.data['relations'].clear(); result.views[0].stored.relation.data['extensions']['evil.value'] = 1
        self.assertEqual(read_project_relation_views(source, b['id']), result)
        with self.assertRaises(FrozenInstanceError): result.views = ()

    def test_bound_source_is_required(self):
        for source in (None, str(self.root), {}, self.root):
            with self.subTest(source=repr(source)), self.assertRaises(TypeError): build_project_relation_index(source)
