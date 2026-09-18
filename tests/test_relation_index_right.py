"""Freshness, partial-cache rejection and independent scan behavior."""
from dataclasses import FrozenInstanceError
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from specroad.graph.indices import RelationIndex
from specroad.graph.references import RelationReferences
from specroad.graph.relations import SourceRelations
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.security import SafetyViolation
from specroad.storage.project import ProjectSource
from specroad.storage.relation_index import (build_project_relation_index, read_project_relation_views,
                                           RelationSourceBinding)
from support.artifacts import artifact_bytes
from support.model import configuration_file, put
from support.relations import aid, artifact, edge, rid
from support.portable import build_distribution, files_under
from test_relation_index import index_of, save


class RelationIndexRightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); configuration_file(self.root)
        self.a = artifact(number=1, relations=[edge(target=aid(number=2))]); self.b = artifact(number=2)
        self.ap = save(self.root, self.a); self.bp = save(self.root, self.b)
        self.source = ProjectSource(self.root)

    def read(self, **kwargs):
        return read_project_relation_views(self.source, self.b['id'], **kwargs)

    def on_read(self, path, action, *, occurrence=1):
        original = self.source.read_normative
        calls = 0
        def read(name, **kwargs):
            nonlocal calls
            result = original(name, **kwargs)
            if name == path:
                calls += 1
                if calls == occurrence: action()
            return result
        return patch.object(self.source, 'read_normative', side_effect=read)

    def test_fresh_hint_and_no_hint_have_identical_complete_results(self):
        cached = build_project_relation_index(self.source)
        self.assertEqual(self.read(index=cached), self.read())

    def test_partial_index_cannot_hide_unselected_incoming_source(self):
        partial = index_of(self.b)
        self.assertEqual(len(partial.for_artifact(self.b['id'])), 0)
        self.assertEqual(tuple(v.relation_id for v in self.read(index=partial).views), (rid(),))

    def test_missing_edge_in_supplied_cache_does_not_change_current_result(self):
        broken = dict(self.a, relations=[]); partial = index_of(broken, self.b)
        self.assertEqual(self.read(index=partial), self.read())

    def test_deleting_disk_cache_is_irrelevant_to_complete_read(self):
        cache = put(self.root, '.specroad/cache/incoming.json', b'{"complete": true, "relations": []}')
        before = self.read(); cache.unlink()
        self.assertEqual(self.read(), before)

    def test_late_source_after_index_build_is_discovered(self):
        cached = build_project_relation_index(self.source)
        save(self.root, artifact(number=65000, relations=[edge(target=self.b['id'], number=7)]))
        result = self.read(index=cached)
        self.assertEqual({v.relation_id for v in result.views}, {rid(), rid(7)})
        self.assertEqual(result.source_count, 3)

    def test_removed_source_is_not_returned_from_old_index(self):
        cached = build_project_relation_index(self.source); self.ap.unlink()
        self.assertEqual(self.read(index=cached).views, ())
        self.assertEqual(self.read(index=cached).source_count, 1)

    def test_removed_selected_target_is_error_not_cached_success(self):
        cached = build_project_relation_index(self.source); self.bp.unlink()
        with self.assertRaises(ModelError): self.read(index=cached)

    def test_corrupt_unselected_source_never_falls_back_to_cached_success(self):
        cached = build_project_relation_index(self.source); self.ap.write_bytes(b'broken')
        with self.assertRaises(ModelError): self.read(index=cached)

    def test_unreadable_current_source_never_falls_back_to_cached_success(self):
        cached = build_project_relation_index(self.source)
        with patch.object(self.source, 'read_normative', side_effect=PermissionError('denied')):
            with self.assertRaises(PermissionError): self.read(index=cached)

    def test_same_size_and_mtime_change_is_detected_by_bytes(self):
        cached = build_project_relation_index(self.source); old = self.ap.stat()
        before = self.ap.read_bytes(); after = before.replace(b'Sample', b'Samplx')
        self.assertEqual(len(before), len(after)); self.ap.write_bytes(after)
        os.utime(self.ap, ns=(old.st_atime_ns, old.st_mtime_ns))
        result = self.read(index=cached)
        self.assertNotEqual(result.binding, cached.binding)
        self.assertEqual(result.views, self.read().views)

    def test_retargeted_relation_not_reused_from_cached_endpoint(self):
        cached = build_project_relation_index(self.source); c = artifact(number=3); save(self.root, c)
        changed = dict(self.a, relations=[edge(target=c['id'])]); save(self.root, changed)
        self.assertEqual(self.read(index=cached).views, ())
        other = read_project_relation_views(self.source, c['id'], index=cached)
        self.assertEqual(tuple(v.relation_id for v in other.views), (rid(),))

    def test_foreign_root_index_is_not_a_local_binding(self):
        cached = build_project_relation_index(self.source)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); configuration_file(root); save(root, self.a); save(root, self.b)
            source = ProjectSource(root)
            result = read_project_relation_views(source, self.b['id'], index=cached)
            self.assertEqual(result.views, self.read().views)
            self.assertNotEqual(result.binding, cached.binding)
            self.assertEqual(result.binding.source_root, str(root.resolve()))

    def test_configuration_change_rejects_old_reader_even_with_hint(self):
        cached = build_project_relation_index(self.source); configuration_file(self.root, project_name='changed')
        with self.assertRaises(ModelError): self.read(index=cached)

    def test_new_reader_with_changed_configuration_gets_new_binding(self):
        cached = build_project_relation_index(self.source); configuration_file(self.root, project_name='changed')
        result = read_project_relation_views(ProjectSource(self.root), self.b['id'], index=cached)
        self.assertNotEqual(result.binding, cached.binding)

    def test_hundreds_of_incoming_sources_are_not_limited_to_display_page(self):
        for n in range(3, 133): save(self.root, artifact(number=n, relations=[edge(target=self.b['id'], number=n)]))
        result = self.read(direction='incoming')
        self.assertEqual(len(result.views), 131)
        self.assertEqual({v.target.id for v in result.views}, {self.a['id']} | {aid(number=n) for n in range(3, 133)})

    def test_retired_source_still_contributes_stored_edges(self):
        save(self.root, dict(self.a, maturity='retired'))
        self.assertEqual(len(self.read().views), 1)

    def test_index_scan_and_fresh_rebuild_agree_after_changes(self):
        cached = build_project_relation_index(self.source)
        save(self.root, artifact(number=6, relations=[edge('depends_on', self.b['id'], number=6)]))
        self.assertEqual(self.read(index=cached), self.read(strategy='scan'))
        self.assertEqual(self.read(), self.read(strategy='scan'))

    def test_scan_path_does_not_need_an_adjacency_index(self):
        with patch('specroad.storage.relation_index.ProjectRelationIndex', side_effect=AssertionError('index unavailable')):
            result = self.read(strategy='scan')
        self.assertEqual(tuple(v.relation_id for v in result.views), (rid(),))

    def test_claimed_complete_mapping_is_not_a_trusted_index(self):
        for index in ({'complete': True, 'entries': []}, [], True, 'cache.json'):
            with self.subTest(index=repr(index)), self.assertRaises(ModelError): self.read(index=index)

    def test_unknown_strategy_is_rejected(self):
        for value in ('cached-only', None, True, 1):
            with self.subTest(value=repr(value)), self.assertRaises(ModelError): self.read(strategy=value)

    def test_new_source_during_read_invalidates_complete_observation(self):
        late = artifact(number=9, relations=[edge(target=self.b['id'], number=9)])
        with self.on_read(str(self.ap.relative_to(self.root)), lambda: save(self.root, late)):
            with self.assertRaises(ModelError): self.read()
        self.assertEqual(len(self.read().views), 2)

    def test_deleted_source_during_read_is_not_silently_dropped(self):
        with self.on_read(str(self.ap.relative_to(self.root)), self.ap.unlink):
            with self.assertRaises((ModelError, FileNotFoundError)): self.read()

    def test_source_byte_change_during_capture_is_error(self):
        def change(): self.ap.write_bytes(self.ap.read_bytes().replace(b'Sample', b'Changed'))
        with self.on_read(str(self.ap.relative_to(self.root)), change):
            with self.assertRaises(ModelError): self.read()

    def test_new_source_during_final_byte_recheck_is_error(self):
        late = artifact(number=9, relations=[edge(target=self.b['id'], number=9)])
        # Two read_source_relations calls for this path, then capture recheck,
        # then the last read recheck. Trigger after graph lookup, not at scan.
        with self.on_read(str(self.ap.relative_to(self.root)), lambda: save(self.root, late), occurrence=4):
            with self.assertRaises(ModelError): self.read()

    def test_symlink_source_is_rejected_without_reading_external_bytes(self):
        self.ap.unlink()
        outside = put(self.root, 'elsewhere.json', artifact_bytes(self.a)); self.ap.symlink_to(outside)
        before = outside.read_bytes()
        with self.assertRaises(SafetyViolation): self.read()
        self.assertEqual(outside.read_bytes(), before)

    def test_nested_project_is_not_combined(self):
        put(self.root, 'spec/requirements/specroad.json', b'{}')
        with self.assertRaises(SafetyViolation): self.read()

    def test_duplicate_relation_identity_from_unselected_source_rejected(self):
        save(self.root, artifact(number=3, relations=[edge(target=self.b['id'])]))
        with self.assertRaises(ModelError) as caught: self.read()
        self.assertEqual(caught.exception.reason, 'duplicate_relation_id')

    def test_wrong_source_path_is_not_treated_as_valid_index_entry(self):
        self.ap.rename(self.ap.with_name(aid(number=7) + '.json'))
        with self.assertRaises(ModelError): self.read()

    def test_cached_objects_and_project_bytes_are_not_modified_by_rebuild(self):
        cached = build_project_relation_index(self.source); previous = cached.binding
        save(self.root, artifact(number=3, relations=[edge(target=self.b['id'], number=3)]))
        before = files_under(self.root); self.read(index=cached)
        self.assertEqual(cached.binding, previous); self.assertEqual(files_under(self.root), before)

    def test_binding_digest_handles_large_local_inode_numbers(self):
        binding = RelationSourceBinding('sample', '/local', (2**64-1, 2**64-2), 'a'*64, ())
        self.assertEqual(len(binding.sha256), 64)
        self.assertNotEqual(binding.sha256, RelationSourceBinding('sample', '/local', (2**64-1, 2**64-3), 'a'*64, ()).sha256)

    def test_observation_binding_is_immutable_and_includes_empty_source(self):
        before = self.read().binding; save(self.root, artifact(number=33))
        after = self.read().binding
        self.assertNotEqual(before.sha256, after.sha256)
        with self.assertRaises(FrozenInstanceError): after.resources = ()

    def test_moved_portable_distributions_keep_complete_inverse_queries(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'built'; build_distribution(output)
            moved = Path(directory) / 'moved'; output.rename(moved)
            for distribution in (moved / 'module', moved / 'specroad.pyz'):
                code = '''import sys
sys.path.insert(0, sys.argv[1])
from specroad.storage.project import ProjectSource
from specroad.storage.relation_index import read_project_relation_views
result = read_project_relation_views(ProjectSource(sys.argv[2]), sys.argv[3])
assert len(result.views) == 1 and result.views[0].inverse
assert result.source_count == 2 and not result.atomic_snapshot
'''
                run = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code, str(distribution), str(self.root), self.b['id']],
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False)
                self.assertEqual(run.returncode, 0, run.stderr.decode())
