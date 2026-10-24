"""Live CLI/direct export publication, invariant normative bytes and failures."""
from hashlib import sha256
import json
from unittest.mock import patch

import pytest

from specroad.cli.application import dispatch_result, execute_request
from specroad.exchange.project_export import export_project
from specroad.graph.scope_descriptors import ScopeDescriptor
from support.domain import domain_value
from support.inspection import inspection_project
from support.model import put
from support.read_only import inventory
from support.scopes import descriptor, query
from test_exchange_export import mapping


def project(root):
    native = inspection_project(root, artifacts=[domain_value('requirement')])
    rule = mapping()
    put(root, 'mappings/export.json', rule.source_bytes)
    return native, rule


@pytest.mark.parametrize('mode', ['cli', 'structured', 'direct'])
def test_export_real_publication_and_normative_inventory(tmp_path, mode):
    root = tmp_path / 'project'
    _, rule = project(root)
    before = inventory(root)
    options = {'--project': str(root), '--scope': 'project', '--mapping': rule.key,
               '--mapping-sha256': rule.sha256, '--output': 'generated/exports/data.ndjson', '--format': 'json'}
    if mode == 'direct':
        result = export_project(root, ScopeDescriptor(descriptor('project')), output=options['--output'],
            output_format='ndjson', mapping_key=rule.key, expected_mapping_sha256=rule.sha256)
    elif mode == 'structured':
        result = execute_request({'command_id': 'export', 'arguments': {'exchange_format': 'ndjson'}, 'options': options}).result
    else:
        result = dispatch_result(['export', 'ndjson', *(item for pair in options.items() for item in pair)])
    assert result.exit_code == 0, result.as_dict()
    data = result.as_dict()['result']
    output = root / options['--output']
    assert output.read_bytes().endswith(b'\n')
    manifest = output.with_name(output.name + '.manifest.json').read_bytes()
    assert json.loads(manifest) == data['manifest']
    assert data['manifest']['output_sha256'] == sha256(output.read_bytes()).hexdigest()
    assert data['manifest']['options'] == {'include_attachments': False, 'fail_on_loss': False}
    after = inventory(root)
    assert tuple(row for row in after if not row[0].startswith('generated')) == before
    assert all(row[0].startswith('generated') for row in set(after) - set(before))


@pytest.mark.parametrize('flags', [[], ['--include-attachments'], ['--fail-on-loss'], ['--include-attachments', '--fail-on-loss']])
def test_export_cli_flags_materialize_and_loss_prohibition_prevents_publication(tmp_path, flags):
    root = tmp_path / 'project'
    _, rule = project(root)
    before = inventory(root)
    result = dispatch_result(['export', 'ndjson', '--project', str(root), '--scope', 'project',
        '--mapping', rule.key, '--mapping-sha256', rule.sha256, '--output', 'generated/exchange.ndjson', *flags])
    if '--fail-on-loss' in flags:
        assert result.exit_code == 3, result.as_dict()
        assert inventory(root) == before
        manifest = result.as_dict()['summary']['unpublished_export_manifest']
    else:
        assert result.exit_code == 0, result.as_dict()
        manifest = result.as_dict()['result']['manifest']
    assert manifest['options'] == {'include_attachments': '--include-attachments' in flags,
                                   'fail_on_loss': '--fail-on-loss' in flags}


def test_export_relocation_cwd_output_and_unchanged_source_bytes(tmp_path):
    root = tmp_path / 'project'
    _, rule = project(root)
    query_path = tmp_path / 'query.json'
    query_path.write_text(json.dumps(query(filters={'type': ['requirement']})))
    outputs = []
    for name in ('first', 'second'):
        external = tmp_path / name
        external.mkdir()
        result = execute_request({'command_id': 'export', 'arguments': {'exchange_format': 'ndjson'},
            'options': {'--project': str(root), '--scope': 'query', '--query': 'query.json',
                '--mapping': rule.key, '--mapping-sha256': rule.sha256, '--output-root': str(external),
                '--output': name + '.ndjson'}}, cwd=tmp_path).result
        assert result.exit_code == 0, result.as_dict()
        outputs.append(((external / (name + '.ndjson')).read_bytes(),
                        (external / (name + '.ndjson.manifest.json')).read_bytes()))
    assert outputs[0] == outputs[1]


@pytest.mark.parametrize('destination', ['spec/requirements/replaced.json', '../outside.ndjson', '.specroad/receipt.json'])
def test_export_forbids_normative_and_unsafe_destinations(tmp_path, destination):
    root = tmp_path / 'project'
    _, rule = project(root)
    before = inventory(root)
    result = export_project(root, ScopeDescriptor(descriptor('project')), output=destination,
        output_format='ndjson', mapping_key=rule.key, expected_mapping_sha256=rule.sha256)
    assert result.exit_code in (3, 7), result.as_dict()
    assert inventory(root) == before


def test_export_detects_source_change_before_any_publication(tmp_path):
    from specroad.exchange import project_export
    root = tmp_path / 'project'
    _, rule = project(root)
    original = project_export.prepare_export
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        put(root, 'mappings/export.json', rule.source_bytes + b' ')
        return result
    with patch.object(project_export, 'prepare_export', changed):
        result = export_project(root, ScopeDescriptor(descriptor('project')), output='generated/export.ndjson',
            output_format='ndjson', mapping_key=rule.key, expected_mapping_sha256=rule.sha256)
    assert result.exit_code == 6, result.as_dict()
    assert not (root / 'generated').exists()


@pytest.mark.parametrize('fmt', ['ndjson', 'csv', 'reqif', 'reqifz'])
@pytest.mark.parametrize('include', [False, True])
def test_export_cli_all_formats_and_actual_attachment_transport(tmp_path, fmt, include):
    from dataclasses import asdict
    from specroad.exchange import merge_reqif_source, decode_reqif_structure, decode_reqifz
    from specroad.mappings import CSVProfile
    from specroad.model.canonical import canonical_json_bytes
    from specroad.model.attachments import AttachmentDescriptor
    from support.records import record_value
    from support.reqif_objects import one, LIMITS
    content = b'owned binary payload\x00\xff'
    attachment = AttachmentDescriptor('attachments/evidence.bin', 'application/octet-stream',
                                      len(content), sha256(content).hexdigest())
    requirement = domain_value('requirement', statement='Bound native statement')
    raw = one()
    context = {'source_system': 'supplier', 'source_document': 'requirements', 'external_revision': None}
    requirement['extensions'] = merge_reqif_source(raw, source_context=context,
        expected_source_sha256=sha256(raw).hexdigest(), extensions={},
        expected_extensions_sha256=sha256(b'{}').hexdigest(), limits=LIMITS)
    root = tmp_path / 'project'
    inspection_project(root, artifacts=[requirement])
    from specroad.model.paths import artifact_path
    evidence = record_value('evidence', attachments=[attachment.data])
    put(root, artifact_path('evidence', evidence['id'], 'SR'), canonical_json_bytes(evidence))
    put(root, attachment.path, content)
    rule = mapping('reqif' if fmt == 'reqifz' else fmt,
        types=[{'external_type': 'type', 'artifact_type': 'requirement'}],
        fields=[{'external_type': 'type', 'external_field': 'field', 'target_field': 'statement', 'value_map': None}],
        relations=[], hierarchies=[])
    put(root, 'mappings/export.json', rule.source_bytes)
    flags = []
    if fmt == 'csv':
        profile = CSVProfile(canonical_json_bytes({'schema_version': '0.2.0',
            'mapping_format_version': 'csv-profile-v1', 'mapping_id': 'example:csv', 'mapping_version': '1.0.0',
            'mapping': rule.binding(), 'external_type': 'type', 'identity': {'column': 'ID', 'kind': 'native_id'},
            'columns': [{'column': 'Text', 'external_field': 'field', 'codec': {'kind': 'string'},
                'empty_cell': 'value', 'missing_column': 'error'}], 'error_policy': 'reject', 'extensions': {}}))
        put(root, 'mappings/csv.json', profile.source_bytes)
        flags += ['--csv-profile', profile.key, '--csv-profile-sha256', profile.sha256]
    if fmt in ('reqif', 'reqifz'):
        limits = tmp_path / 'limits.json'
        limits.write_text(json.dumps(asdict(LIMITS)))
        flags += ['--xml-limits', str(limits)]
    if fmt == 'reqifz':
        flags += ['--max-archive-bytes', str(20*1024*1024)]
    before = inventory(root)
    output = root / ('generated/out/data.' + fmt)
    result = dispatch_result(['export', fmt, '--project', str(root), '--scope', 'project',
        '--mapping', rule.key, '--mapping-sha256', rule.sha256, '--output', str(output.relative_to(root)),
        *flags, *(['--include-attachments'] if include else [])])
    assert result.exit_code == 0, result.as_dict()
    manifest = result.as_dict()['result']['manifest']
    data = output.read_bytes()
    assert manifest['attachments'] == [{**attachment.data, 'included': include}]
    assert manifest['output_sha256'] == sha256(data).hexdigest()
    assert json.loads(output.with_name(output.name + '.manifest.json').read_bytes()) == manifest
    if fmt == 'reqifz':
        container = decode_reqifz(data, expected_sha256=sha256(data).hexdigest(),
            document_paths=('exchange.reqif',), limits=LIMITS, max_uncompressed_bytes=20*1024*1024)
        files = dict(container.files)
        assert set(files) == ({'exchange.reqif', attachment.path} if include else {'exchange.reqif'})
        if include:
            assert files[attachment.path] == content
        xml = files['exchange.reqif']
    elif include:
        assert (output.parent / attachment.path).read_bytes() == content
    else:
        assert not (output.parent / 'attachments').exists()
    if fmt in ('reqif', 'reqifz'):
        parsed = decode_reqif_structure(xml if fmt == 'reqifz' else data, limits=LIMITS)
        assert parsed.project_record(parsed.objects[0].identifier)['fields']['field'] == requirement['statement']
    elif fmt == 'csv':
        assert data == ('ID,Text\r\n' + requirement['id'] + ',Bound native statement\r\n').encode()
    else:
        assert requirement in [json.loads(line)['object'] for line in data.splitlines()]
    assert tuple(row for row in inventory(root) if not row[0].startswith('generated')) == before


def test_export_project_includes_real_historical_baseline_objects(tmp_path):
    from test_baseline_creation import project as baseline_project, plan_for, apply
    from specroad.authoring._inspection_snapshot import InspectionSnapshot
    root = tmp_path / 'project'
    original = baseline_project(root, bundled=True)
    plan = plan_for(original)
    apply(plan, original)
    rule = mapping()
    put(root, 'mappings/export.json', rule.source_bytes)
    before = inventory(root)
    snapshot = InspectionSnapshot(root, None, include_archive_objects=True)
    result = export_project(root, ScopeDescriptor(descriptor('project')), output='generated/baseline.ndjson',
        output_format='ndjson', mapping_key=rule.key, expected_mapping_sha256=rule.sha256)
    assert result.exit_code == 0, result.as_dict()
    manifest = result.as_dict()['result']['manifest']
    baseline = plan.data['operations'][0]['record']
    assert baseline['id'] in manifest['included_ids']
    assert manifest['model_root_sha256'] == snapshot.model.manifest(snapshot.model.artifacts, descriptor('project')).sha256
    historical = {row['object_path'] for row in baseline['manifest']}
    assert historical <= {row['resource_id'] for row in manifest['losses']}
    assert tuple(row for row in inventory(root) if not row[0].startswith('generated')) == before


@pytest.mark.parametrize('kind', ['core', 'pyz'])
def test_export_in_isolated_portable_distribution(tmp_path, kind):
    from support.portable import build_distribution
    from support.processes import run_core, run_python
    root = tmp_path / 'project'
    _, rule = project(root)
    core, pyz = build_distribution(tmp_path / 'distribution')
    argv = ['export', 'ndjson', '--scope', 'project', '--mapping', rule.key,
            '--mapping-sha256', rule.sha256, '--output', 'generated/portable.ndjson', '--format', 'json']
    observed = (run_core('from specroad.cli import main\nraise SystemExit(main(' + repr(argv) + '))', root, capture=True) if kind == 'core' else
                run_python(['-I', '-S', '-B', str(pyz), *argv], root, capture=True))
    assert observed.returncode == 0, observed.stderr
    envelope = json.loads(observed.stdout)
    output = root / 'generated/portable.ndjson'
    assert envelope['result']['manifest']['output_sha256'] == sha256(output.read_bytes()).hexdigest()
    assert json.loads(output.read_bytes())['object']['id'] == domain_value('requirement')['id']
