"""14.n.W: actual local imports and an initial hostile byte-input corpus."""
from dataclasses import asdict
from hashlib import sha256
import json
import stat

import pytest

from specroad.exchange import encode_reqifz
from specroad.mappings import CSVProfile, ExchangeMapping
from specroad.model.canonical import canonical_json_bytes
from specroad.model.paths import artifact_path
from support.csv_codec import column
from support.exchange_mappings import mapping_value
from support.folds import goal
from support.import_execution import PAYLOAD, project
from support.import_security import IMPORTS, run_isolated
from support.ndjson_codec import envelope
from support.read_only import inventory
from support.reqif_objects import LIMITS, document, datatype, definition, spec_object, value
from support.targets import ACTOR, TIME, SCOPE
from test_work_archive import foreign_zip


# Executable-looking values and remote locations remain literal supplier data.
TEXT = "Literal $(touch CONVERTER_RAN); https://supplier.invalid/data; 日本語 & <value>."
IDENTITY = {'source_system': 'supplier', 'source_document': 'explicit-document',
            'external_id': 'external-1', 'external_revision': '1'}


def input_resources(fmt):
    external_type, field = ('type', 'field') if fmt in ('reqif', 'reqifz') else ('Goal', 'Text')
    resource = ExchangeMapping(canonical_json_bytes(mapping_value(
        source_format='reqif' if fmt == 'reqifz' else fmt,
        types=[{'external_type': external_type, 'artifact_type': 'goal'}],
        fields=[{'external_type': external_type, 'external_field': field,
                 'target_field': 'statement', 'value_map': None}], relations=[], hierarchies=[])))
    profile = CSVProfile(canonical_json_bytes({
        'schema_version': '0.2.0', 'mapping_format_version': 'csv-profile-v1',
        'mapping_id': 'example:security-csv', 'mapping_version': '1.0.0',
        'mapping': resource.binding(), 'external_type': external_type,
        'identity': {'column': 'ID', 'kind': 'external_id'}, 'columns': [column('Text')],
        'error_policy': 'reject', 'extensions': {}})) if fmt == 'csv' else None
    if fmt == 'csv':
        raw = ('ID,Text\r\nexternal-1,' + TEXT + '\r\n').encode()
    elif fmt == 'ndjson':
        raw = canonical_json_bytes(envelope(goal(statement=TEXT, external_identities=[]))) + b'\n'
    else:
        raw = document(datatypes=datatype('STRING'), definitions=definition('STRING', 'field', 'dt'),
                       objects=spec_object(value('STRING', 'field', TEXT), identifier='external-1'))
        if fmt == 'reqifz':
            raw = encode_reqifz({'document.reqif': raw, 'unused.txt': b'passive only'},
                document_paths=['document.reqif'], limits=LIMITS, max_uncompressed_bytes=8*1024*1024)
    return raw, resource, profile


def target_setup(root, model, resource):
    paths = {artifact_path(a['artifact_type'], a['id'], 'SR') for a in model.artifacts}
    documents = [(p, b) for p, b in model.source_files.items() if p in paths]
    resources = [(p, b) for p, b in model.source_files.items() if p not in paths and p != 'specroad.json']
    return ('root=Path(' + repr(str(root)) + '); st=root.stat()\n'
        + 'p=ProfileResource(' + repr(model.profile_resources[0].source_bytes) + ')\n'
        + 'm=TargetModel(' + repr(model.configuration_bytes)
        + ",ProjectReadBinding('sample',str(root),(st.st_dev,st.st_ino)),"
        + '[ModelDocument(p,b) for p,b in ' + repr(documents) + '],'
        + 'profile=compose_profiles([p],core_key=p.key),'
        + 'resource_files=[ModelDocument(p,b) for p,b in ' + repr(resources) + '],'
        + 'attachments=[AttachmentDescriptor(**d) for d in '
        + repr([d.data for d in model.attachment_descriptors]) + '])\n'
        + 'resource=ExchangeMapping(' + repr(resource.source_bytes) + ')\n')


@pytest.mark.parametrize('mode', ['core', 'pyz'])
@pytest.mark.parametrize('fmt', ['csv', 'ndjson', 'reqif', 'reqifz'])
def test_allowed_bytes_reach_real_native_import_with_network_and_converters_disabled(tmp_path, fmt, mode):
    sandbox = tmp_path / 'sandbox'; sandbox.mkdir()
    raw, resource, profile = input_resources(fmt)
    root = sandbox / 'project'; model, resource = project(root, resource=resource)
    before_foreign = (root / 'foreign.bin').read_bytes()
    body = IMPORTS + target_setup(root, model, resource)
    body += 'raw=' + repr(raw) + '\nfmt=' + repr(fmt) + '\nlimits=ReqIFLimits(**' + repr(asdict(LIMITS)) + ')\n'
    body += 'identity=' + repr(IDENTITY) + '\n'
    if fmt == 'csv':
        body += 'profile=CSVProfile(' + repr(profile.source_bytes) + ')\n'
    body += "phase='parse'\n"
    body += '''
if fmt == 'csv':
    observation = select_csv_profile([profile, resource], key=profile.key,
        expected_sha256=profile.sha256).decode(raw)
    row, = observation.records
    assert row['identity'] == {'kind': 'external_id', 'value': identity['external_id']}
    fields, external_type = row['fields'], row['external_type']
elif fmt == 'ndjson':
    observation = decode_ndjson(raw)
    row, = observation.objects
    assert row['object_kind'] == 'artifact' and row['object']['artifact_type'] == 'goal'
    fields, external_type = {'Text': row['object']['statement']}, 'Goal'
else:
    xml = raw
    if fmt == 'reqifz':
        container = decode_reqifz(raw, expected_sha256=sha256(raw).hexdigest(),
            document_paths=['document.reqif'], limits=limits, max_uncompressed_bytes=8*1024*1024)
        xml = container.files['document.reqif']
        assert container.files['unused.txt'] == b'passive only'
    observation = decode_reqif_structure(xml, limits=limits)
    row = observation.project_object(identity['external_id'])
    fields, external_type = row['fields'], row['external_type']
assert not attempts
values = [{'identity': identity, 'external_type': external_type, 'fields': fields, 'new_artifact': None}]
def check_mapping(c):
    ExchangeMapping(resource.source_bytes)
    return c.result()
g = ModelGate('extension:target-resources', 'isolated-security-mapping-v1',
    lambda c: c.dependency_result({i: [] for i in c.subjects}), check_mapping, resource.source_sha256)
# The host explicitly authorizes this synthetic owned project transaction.
# It does not treat parser output or an external source as write permission.
phase = 'publish'
'''
    body += ('result=apply_import_plan(m,values,input_format=fmt,input_bytes=raw,mapping_resources=[resource],'
        + 'mapping_key=resource.key,mapping_sha256=resource.sha256,strategy="update_if_unchanged",'
        + 'change_plan_id="CP-security",request_id="request-security",actor=' + repr(ACTOR)
        + ',planned_at=' + repr(TIME) + ',scope_descriptor=' + repr(SCOPE)
        + ',metadata_policy_version="change-metadata-v1",policy=TargetPolicy("import","1",()),'
        + 'gates=[g],transaction_id="txn-security",authority=PublicationAuthority("owned-security-host","1",lambda r:True))\n'
        + "assert not attempts\nprint(json.dumps({'result':result,'attempts':attempts}))\n")
    process = run_isolated(body, sandbox, mode=mode)
    assert process.returncode == 0, process.stderr
    actual = json.loads(process.stdout); result = actual['result']
    assert actual['attempts'] == []
    assert result['execution']['write_state'] == 'committed'
    assert result['execution']['completion']['current_target_verified']
    assert result['execution']['completion']['cleanup_completed']
    old, = [a for a in model.artifacts if a.get('external_identities')]
    target_path = artifact_path('goal', old['id'], 'SR')
    saved = json.loads((root / target_path).read_bytes())
    assert saved['statement'] == TEXT and saved['revision'] == old['revision'] + 1
    assert saved['external_identities'][0]['last_source_payload_sha256'] == sha256(raw).hexdigest()
    assert result['submitted_import_plan']['updated_ids'] == [old['id']]
    for path, content in model.source_files.items():
        if path != target_path:
            assert (root / path).read_bytes() == content
    assert (root / 'foreign.bin').read_bytes() == before_foreign
    assert (root / 'attachments/supplier.bin').read_bytes() == PAYLOAD
    assert not (sandbox / 'CONVERTER_RAN').exists() and not (root / 'CONVERTER_RAN').exists()


def rejection(raw, parser, *, expected_reason, expected_exit):
    body = IMPORTS + 'raw=' + repr(raw) + '\nparser=' + repr(parser) + '\n'
    body += 'limits=ReqIFLimits(**' + repr(asdict(LIMITS)) + ')\n'
    body += "phase='parse'\n"
    body += '''
try:
    if parser == 'reqif': decode_reqif(raw, limits=limits)
    elif parser == 'reqif-structure': decode_reqif_structure(raw, limits=limits)
    elif parser == 'reqifz':
        decode_reqifz(raw, expected_sha256=sha256(raw).hexdigest(),
            document_paths=['document.reqif'], limits=limits, max_uncompressed_bytes=8*1024*1024)
    elif parser == 'junit': JUnitDocument(raw)
    elif parser == 'mapping': ExchangeMapping(raw)
    elif parser == 'csv-profile': CSVProfile(raw)
    else: raise AssertionError('unknown trusted fixture parser')
except ModelError as error:
    result = {'reason': error.reason, 'exit_code': error.exit_code}
else:
    raise AssertionError('hostile input accepted')
assert not attempts
print(json.dumps({'error': result, 'attempts': attempts}))
'''
    expected = {'error': {'reason': expected_reason, 'exit_code': expected_exit}, 'attempts': []}
    return body, expected


@pytest.mark.parametrize('mode', ['core', 'pyz'])
@pytest.mark.parametrize('parser', ['reqif', 'reqif-structure', 'reqifz', 'junit'])
@pytest.mark.parametrize('location', ['network', 'local-file'])
def test_external_entities_are_refused_before_any_resolution_or_write(tmp_path, mode, parser, location):
    sandbox = tmp_path / 'sandbox'; sandbox.mkdir()
    canary = sandbox / 'private.txt'; canary.write_bytes(b'owned secret must not be read')
    uri = canary.as_uri() if location == 'local-file' else 'https://supplier.invalid/external'
    root_name = 'testsuite' if parser == 'junit' else 'REQ-IF'
    raw = ('<!DOCTYPE ' + root_name + ' [<!ENTITY leak SYSTEM "' + uri + '">]><'
           + root_name + '>&leak;</' + root_name + '>').encode()
    if parser == 'reqifz':
        raw = foreign_zip([('document.reqif', raw)])
    body, expected = rejection(raw, parser, expected_reason='xml_dtd_or_entity_forbidden', expected_exit=7)
    before = inventory(sandbox)
    process = run_isolated(body, sandbox, mode=mode)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == expected and inventory(sandbox) == before


@pytest.mark.parametrize('mode', ['core', 'pyz'])
@pytest.mark.parametrize('case', ['traversal', 'absolute', 'symlink'])
def test_unselected_hostile_archive_members_are_refused_without_extraction(tmp_path, mode, case):
    sandbox = tmp_path / 'sandbox'; sandbox.mkdir()
    canary = sandbox / 'private.txt'; canary.write_bytes(b'owned unchanged bytes')
    name = '../escape.txt' if case == 'traversal' else str(canary) if case == 'absolute' else 'link'
    change = (lambda info: setattr(info, 'external_attr', (stat.S_IFLNK | 0o777) << 16)
              if info.filename == name else None) if case == 'symlink' else None
    raw = foreign_zip(sorted([('document.reqif', document()), (name, b'untrusted bytes')]), change=change)
    reason = 'unsafe_archive_entry' if case == 'symlink' else 'unsafe_archive_path'
    body, expected = rejection(raw, 'reqifz', expected_reason=reason, expected_exit=7)
    before = inventory(sandbox)
    process = run_isolated(body, sandbox, mode=mode)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == expected and inventory(sandbox) == before
    assert not (tmp_path / 'escape.txt').exists()


@pytest.mark.parametrize('mode', ['core', 'pyz'])
@pytest.mark.parametrize('parser', ['mapping', 'csv-profile'])
def test_executable_converter_declarations_are_not_part_of_the_data_grammar(tmp_path, mode, parser):
    sandbox = tmp_path / 'sandbox'; sandbox.mkdir()
    _, mapping, profile = input_resources('csv')
    value = mapping.data if parser == 'mapping' else profile.data
    declaration = value['fields'][0] if parser == 'mapping' else value['columns'][0]['codec']
    declaration['converter'] = 'touch CONVERTER_RAN; curl https://supplier.invalid/data'
    body, expected = rejection(canonical_json_bytes(value), parser,
                               expected_reason='mapping_unknown_field', expected_exit=3)
    before = inventory(sandbox)
    process = run_isolated(body, sandbox, mode=mode)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == expected and inventory(sandbox) == before


@pytest.mark.parametrize('call,event', [
    ('socket.socket()', 'socket.__new__'),
    ("socket.getaddrinfo('127.0.0.1', 80)", 'socket.getaddrinfo'),
    ("subprocess.run([sys.executable, '-I', '-S', '-B', '-c', 'raise SystemExit(97)'])", 'subprocess.Popen'),
    ("os.system('exit 97')", 'os.system'),
], ids=['socket', 'resolver', 'process', 'shell'])
def test_isolated_probe_really_denies_and_records_runtime_effects(tmp_path, call, event):
    sandbox = tmp_path / 'sandbox'; sandbox.mkdir()
    body = "try:\n    " + call + "\nexcept ForbiddenEffect:\n    pass\nelse:\n    raise AssertionError('guard inactive')\n"
    body += 'print(json.dumps(attempts))\n'
    process = run_isolated(body, sandbox)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == [event]
