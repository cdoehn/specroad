"""Publication races and failure boundaries leave normative sources untouched."""
from hashlib import sha256
import json
import os
from unittest.mock import patch

import pytest

from specroad.exchange import project_export
from specroad.exchange.project_export import export_project
from specroad.cli.application import dispatch_result
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.model.canonical import canonical_json_bytes
from specroad.model.paths import artifact_path
from specroad.security import ProjectBoundary
from support.domain import domain_value
from support.model import put
from support.read_only import inventory
from support.records import record_value
from support.scopes import descriptor, query
from test_project_export import project


def invoke(root, rule, **options):
    return export_project(root, ScopeDescriptor(descriptor('project')),
        **({'output': 'generated/export.ndjson', 'output_format': 'ndjson',
            'mapping_key': rule.key, 'expected_mapping_sha256': rule.sha256} | options))


def attached_project(root):
    from specroad.model.attachments import AttachmentDescriptor
    _, rule = project(root)
    raw = b'actual scoped attachment'
    attachment = AttachmentDescriptor('attachments/report.bin', 'application/octet-stream', len(raw), sha256(raw).hexdigest())
    evidence = record_value('evidence', attachments=[attachment.data])
    put(root, artifact_path('evidence', evidence['id'], 'SR'), canonical_json_bytes(evidence))
    put(root, attachment.path, raw)
    return rule, attachment, raw


@pytest.mark.parametrize('source', ['artifact', 'mapping', 'profile', 'configuration', 'added_artifact', 'deleted_artifact'])
def test_export_each_source_mutation_after_preparation_prevents_publication(tmp_path, source):
    root = tmp_path / 'project'
    _, rule = project(root)
    artifact = artifact_path('requirement', domain_value('requirement')['id'], 'SR')
    path = {'artifact': artifact, 'mapping': 'mappings/export.json', 'profile': 'profiles/core.json',
            'configuration': 'specroad.json', 'deleted_artifact': artifact,
            'added_artifact': artifact_path('goal', domain_value('goal')['id'], 'SR')}[source]
    original = project_export.prepare_export
    observed = []
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        if source == 'deleted_artifact':
            (root / path).unlink()
        elif source == 'added_artifact':
            put(root, path, canonical_json_bytes(domain_value('goal')))
        else:
            put(root, path, (root / path).read_bytes() + b' ')
        observed.append(inventory(root))
        return result
    with patch.object(project_export, 'prepare_export', changed):
        result = invoke(root, rule)
    assert result.exit_code == 6, result.as_dict()
    assert not (root / 'generated').exists()
    assert inventory(root) == observed[0]


@pytest.mark.parametrize('changed_input', ['source', 'query'])
def test_export_source_change_during_final_output_read_cannot_return_success(tmp_path, changed_input):
    root = tmp_path / 'project'
    _, rule = project(root)
    input_path = tmp_path / 'query.json'
    input_bytes = canonical_json_bytes(query())
    input_path.write_bytes(input_bytes)
    original = ProjectBoundary.read_bytes
    changed = []
    def read(boundary, name, *args, **kwargs):
        raw = original(boundary, name, *args, **kwargs)
        if name == 'generated/export.ndjson.manifest.json' and not changed:
            target = root / 'mappings/export.json' if changed_input == 'source' else input_path
            target.write_bytes(target.read_bytes() + b' ')
            changed.append(True)
        return raw
    with patch.object(ProjectBoundary, 'read_bytes', read):
        result = invoke(root, rule, input_bindings=((ProjectBoundary(tmp_path), 'query.json', input_bytes),))
    assert changed
    assert result.exit_code == 6, result.as_dict()
    assert not result.as_dict().get('result')


@pytest.mark.parametrize('kind', ['file', 'symlink', 'hardlink', 'directory', 'manifest'])
def test_export_existing_targets_never_overwritten(tmp_path, kind):
    root = tmp_path / 'project'
    _, rule = project(root)
    target = root / 'generated/export.ndjson'
    target.parent.mkdir()
    source = tmp_path / 'unchanged'
    source.write_bytes(b'unchanged')
    if kind == 'symlink':
        target.symlink_to(source)
    elif kind == 'hardlink':
        os.link(source, target)
    elif kind == 'directory':
        target.mkdir()
    elif kind == 'manifest':
        target.with_name(target.name + '.manifest.json').write_bytes(b'previous manifest')
    else:
        target.write_bytes(b'previous export')
    before = inventory(root)
    result = invoke(root, rule)
    assert result.exit_code == 6, result.as_dict()
    assert inventory(root) == before and source.read_bytes() == b'unchanged'


@pytest.mark.parametrize('kind', ['symlink', 'foreign_project'])
def test_export_unsafe_existing_parent_is_rejected_without_writes(tmp_path, kind):
    root = tmp_path / 'project'
    _, rule = project(root)
    external = tmp_path / 'external'
    external.mkdir()
    nested = external / 'nested'
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    if kind == 'symlink':
        nested.symlink_to(elsewhere, target_is_directory=True)
    else:
        nested.mkdir()
        (nested / 'specroad.json').write_bytes(b'{}')
    before = inventory(root), inventory(external), inventory(elsewhere)
    result = invoke(root, rule, output_root=external, output='nested/spec/requirements/new.json')
    assert result.exit_code == 7, result.as_dict()
    assert (inventory(root), inventory(external), inventory(elsewhere)) == before


def test_export_late_create_race_is_conflict_not_overwrite(tmp_path):
    root = tmp_path / 'project'
    _, rule = project(root)
    def raced(*args, **kwargs):
        put(root, 'generated/export.ndjson', b'concurrent writer')
        raise FileExistsError('concurrent target creation')
    with patch.object(project_export, 'replace_bound_image', raced):
        result = invoke(root, rule)
    assert result.exit_code == 6, result.as_dict()
    assert (root / 'generated/export.ndjson').read_bytes() == b'concurrent writer'
    assert not (root / 'generated/export.ndjson.manifest.json').exists()


def test_export_partial_io_failure_keeps_complete_images_without_success(tmp_path):
    root = tmp_path / 'project'
    _, rule = project(root)
    before = inventory(root)
    original = project_export.replace_bound_image
    count = []
    def fail_second(*args, **kwargs):
        count.append(True)
        if len(count) == 2:
            raise OSError('synthetic unavailable output')
        return original(*args, **kwargs)
    with patch.object(project_export, 'replace_bound_image', fail_second):
        result = invoke(root, rule)
    assert result.exit_code == 5, result.as_dict()
    assert len(count) == 2
    assert json.loads((root / 'generated/export.ndjson').read_bytes())['object'] == domain_value('requirement')
    assert not (root / 'generated/export.ndjson.manifest.json').exists()
    assert tuple(row for row in inventory(root) if not row[0].startswith('generated')) == before


@pytest.mark.parametrize('name', ['attachments', 'ATTACHMENTS'])
def test_export_file_parent_collision_is_rejected_before_any_image(tmp_path, name):
    root = tmp_path / 'project'
    rule, _, _ = attached_project(root)
    before = inventory(root)
    result = invoke(root, rule, output='generated/out/' + name, include_attachments=True)
    assert result.exit_code == 6, result.as_dict()
    assert inventory(root) == before


@pytest.mark.parametrize('include', [False, True])
@pytest.mark.parametrize('change', ['replace', 'remove'])
def test_export_changed_attachment_is_not_downgraded_by_transport_flag(tmp_path, include, change):
    root = tmp_path / 'project'
    rule, attachment, _ = attached_project(root)
    original = project_export.prepare_export
    observed = []
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        if change == 'remove':
            (root / attachment.path).unlink()
        else:
            put(root, attachment.path, b'changed payload')
        observed.append(inventory(root))
        return result
    with patch.object(project_export, 'prepare_export', changed):
        result = invoke(root, rule, include_attachments=include, fail_on_loss=False)
    assert result.exit_code == 6, result.as_dict()
    assert inventory(root) == observed[0]


@pytest.mark.parametrize('include', [False, True])
def test_export_missing_attachment_source_prevents_output(tmp_path, include):
    root = tmp_path / 'project'
    rule, attachment, _ = attached_project(root)
    (root / attachment.path).unlink()
    before = inventory(root)
    result = invoke(root, rule, include_attachments=include, fail_on_loss=False)
    assert result.exit_code == 5, result.as_dict()
    assert inventory(root) == before


@pytest.mark.parametrize('target', ['primary', 'attachment'])
def test_export_final_output_tampering_prevents_success(tmp_path, target):
    root = tmp_path / 'project'
    rule, attachment, _ = attached_project(root)
    original = project_export.replace_bound_image
    def replace_image(*args, **kwargs):
        value = original(*args, **kwargs)
        if args[3] == 'export.ndjson.manifest.json':
            name = 'generated/export.ndjson' if target == 'primary' else 'generated/' + attachment.path
            put(root, name, b'tampered')
        return value
    with patch.object(project_export, 'replace_bound_image', replace_image):
        result = invoke(root, rule, include_attachments=True)
    assert result.exit_code == 6, result.as_dict()


@pytest.mark.parametrize('fmt', ['ndjson', 'csv', 'reqif'])
def test_export_cli_archive_limit_cannot_be_silently_ignored(tmp_path, fmt):
    from dataclasses import asdict
    from support.reqif_objects import LIMITS
    from test_exchange_export import mapping
    root = tmp_path / 'project'
    project(root)
    rule = mapping(fmt)
    put(root, 'mappings/export.json', rule.source_bytes)
    flags = []
    if fmt == 'reqif':
        path = tmp_path / 'limits.json'
        path.write_text(json.dumps(asdict(LIMITS)))
        flags = ['--xml-limits', str(path)]
    before = inventory(root)
    result = dispatch_result(['export', fmt, '--project', str(root), '--scope', 'project',
        '--mapping', rule.key, '--mapping-sha256', rule.sha256, '--output', 'generated/export.' + fmt,
        '--max-archive-bytes', '1', *flags])
    assert result.exit_code == 2, result.as_dict()
    assert inventory(root) == before
