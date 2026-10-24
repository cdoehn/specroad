"""Real codecs and native projects for the explicit-candidate Work adapter.

The test host supplies identity context, creation envelopes, policy and human
authority explicitly. This is not an end-user import CLI or a foreign tool.
"""
from hashlib import sha256

from specroad.cli.contracts import (CommandClass, CommandSpec, CommandProtocol,
                                    EffectScope, PreflightProfile)
from specroad.cli.registry import CommandRegistry
from specroad.exchange import (decode_ndjson, encode_ndjson, decode_reqif_structure,
    decode_reqifz, encode_reqifz, select_csv_profile)
from specroad.exchange.import_work import prepare_import_work, advance_import_work
from specroad.mappings import CSVProfile
from specroad.model.canonical import canonical_json_bytes
from specroad.runtime.consumption import WorkConsumption
from specroad.security import ProjectBoundary
from specroad.work.checkpoints import CheckpointStore
from specroad.work.root import WorkDirectory
from specroad.validation import ModelGate
from support.csv_codec import column
from support.exchange_oracles import assert_review_status
from support.folds import goal
from support.import_execution import project, inputs
from support.import_planning import candidate, identity, imported, mapping
from support.ndjson_codec import envelope
from support.read_only import no_write_attempts
from support.relations import edge
from support.reqif_objects import LIMITS, datatype, definition, document, spec_object, value
from test_relation_review_status import review
from test_work_progress import unknown

FORMATS = ('csv', 'ndjson', 'reqif', 'reqifz')


def registry():
    def unused(invocation):
        raise AssertionError('No execution code is read from Work storage')
    return CommandRegistry((CommandSpec('import.plan', ('import', 'plan'), CommandClass.READ_ONLY,
        PreflightProfile.BOOTSTRAP, EffectScope.NONE, unused,
        protocol=CommandProtocol('import-plan-work-v1', {'command_id': 'import.plan'},
                                 handler_exit_codes=(0, 3, 5))),))


def transport(fmt):
    resource = mapping(source_format='reqif' if fmt == 'reqifz' else fmt)
    texts = ['Updated supplier goal.', 'Unicode é e\u0301 日本語', 'Third, "quoted" value', 'Final object']
    keys = ['external-' + str(n + 1) for n in range(len(texts))]
    profile = None
    if fmt == 'csv':
        profile = CSVProfile(canonical_json_bytes({
            'schema_version': '0.2.0', 'mapping_format_version': 'csv-profile-v1',
            'mapping_id': 'fixture:import-csv', 'mapping_version': '1.0.0',
            'mapping': resource.binding(), 'external_type': 'Goal',
            'identity': {'column': 'ID', 'kind': 'external_id'}, 'columns': [column('Text')],
            'error_policy': 'reject', 'extensions': {}}))
        codec = select_csv_profile([resource, profile], key=profile.key, expected_sha256=profile.sha256)
        raw = codec.encode([{'identity': {'kind': 'external_id', 'value': k},
                            'external_type': 'Goal', 'fields': {'Text': text}} for k, text in zip(keys, texts)])
        parsed = [(row['identity']['value'], row['fields']['Text']) for row in codec.decode(raw).records]
    elif fmt == 'ndjson':
        raw = encode_ndjson([envelope(goal(n, statement=text, external_identities=[identity(k)]))
                            for n, (k, text) in enumerate(zip(keys, texts))])
        parsed = [(row['object']['external_identities'][0]['external_id'], row['object']['statement'])
                  for row in decode_ndjson(raw).objects]
    else:
        xml = document(datatypes=datatype('STRING'), definitions=definition('STRING', 'Text', 'dt'),
            objects=''.join(spec_object(value('STRING', 'Text', text), identifier=k, type_id='Goal')
                            for k, text in zip(keys, texts))).replace(b'IDENTIFIER="type"', b'IDENTIFIER="Goal"')
        raw = xml
        if fmt == 'reqifz':
            options = dict(document_paths=('source.reqif',), limits=LIMITS, max_uncompressed_bytes=8*1024*1024)
            raw = encode_reqifz({'source.reqif': xml}, **options)
            xml = decode_reqifz(raw, expected_sha256=sha256(raw).hexdigest(), **options).files['source.reqif']
        decoded = decode_reqif_structure(xml, limits=LIMITS)
        parsed = [(o.identifier, decoded.project_record(o.identifier)['fields']['Text']) for o in decoded.objects]
    assert parsed == list(zip(keys, texts))
    candidates = [candidate(text, number=n, key=k, new=n != 0) for n, (k, text) in enumerate(parsed)]
    return resource, profile, raw, candidates


def setup(tmp_path, fmt='ndjson', *, mutate=None, publish=True):
    resource, profile, raw, candidates = transport(fmt)
    target = goal(9)
    source = imported(relations=[edge('supersedes', target['id'])])
    values = [source, target, review(source, target, time='2026-06-30T12:00:00Z')]
    native, _ = project(tmp_path / 'project', artifacts=values, resource=resource)
    # The explicit CSV conversion profile is a bound project resource. The
    # adapter still labels candidates as host-parsed; it infers no profile.
    if profile is not None:
        from specroad.changes.target_model import TargetModel
        from specroad.validation import ModelDocument
        path = 'mappings/csv-profile.json'
        native = TargetModel(native.configuration_bytes, native.binding, native.documents,
            profile=native.profile, attachments=native.attachment_descriptors,
            resource_files=[*native.resource_files, ModelDocument(path, profile.source_bytes)])
        (tmp_path / 'project' / path).write_bytes(profile.source_bytes)
    options = {**inputs(resource), 'input_format': fmt, 'input_bytes': raw}
    if profile is not None:
        def check_resources(context):
            checked = select_csv_profile([resource, profile], key=profile.key,
                                         expected_sha256=profile.sha256)
            assert checked.decode(raw).records
            return context.result()
        options['gates'] = [ModelGate('extension:target-resources', 'synthetic-import-work-resources-v1',
            lambda c: c.dependency_result({i: [] for i in c.subjects}), check_resources,
            sha256(resource.source_bytes + profile.source_bytes).hexdigest())]
    # Only an unchanged synthetic retained review is admitted by these host
    # fixtures. They authenticate no real human and recompute native status.
    retained = values[-1]; retained_bytes = canonical_json_bytes(retained)
    def check_review(context):
        actual = {i: context.artifact(i) for i in context.all_ids}
        assert set(context.subjects) == {retained['id']}
        assert canonical_json_bytes(actual[retained['id']]) == retained_bytes
        expected = 'current' if actual[source['id']] == source else 'suspect'
        assert_review_status(actual.values(), source['id'], source['relations'][0]['relation_id'], expected)
        return context.result()
    options['gates'] += [ModelGate(name, 'synthetic-retained-review-v1',
        lambda c: c.dependency_result({i: list(c.all_ids) for i in c.subjects}),
        check_review, sha256(retained_bytes).hexdigest()) for name in ('lifecycle', 'review_currentness')]
    if mutate: mutate(native, candidates, options)
    with no_write_attempts():
        initial = prepare_import_work(registry(), native, candidates,
                                       **{k: v for k, v in options.items() if k != 'gates'})
    location = WorkDirectory(initial, protected_roots=(ProjectBoundary(native.binding.source_root),),
                             directory=tmp_path / 'work')
    store = CheckpointStore(location, initial)
    if publish: store.publish(initial)
    return native, candidates, options, initial, store


def advance(store, options, *, size=1, profile='constrained', sampler=unknown, limits=None):
    call = WorkConsumption(sampler=sampler).begin({'--resource-profile': profile, **(limits or {})})
    try:
        result = advance_import_work(store, call, registry=registry(), policy=options['policy'],
                                      gates=options['gates'], max_units=size)
    finally:
        measured = call.finish()
    return result, measured


def reopen(initial, path, project):
    return CheckpointStore(WorkDirectory(initial, protected_roots=(ProjectBoundary(project),),
                                         directory=path), initial)
