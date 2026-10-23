"""Owned native projects for explicit artifact-candidate import execution.

Supplier bytes are synthetic and already parsed by the test host. This fixture
does not implement a source parser or fabricate product approval evidence.
"""
from hashlib import sha256

from specroad.changes import PublicationAuthority
from specroad.exchange import apply_import_plan, prepare_import_plan
from specroad.mappings import ExchangeMapping
from specroad.model.attachments import AttachmentDescriptor
from specroad.model.model_manifest import ProjectReadBinding
from specroad.validation import ModelDocument, ModelGate
from support.folds import goal
from support.import_planning import PAYLOAD, candidate, imported, mapping
from support.model import put
from support.targets import ACTOR, TIME, POLICY, SCOPE, model

ALLOW = PublicationAuthority('synthetic-import-host', '1', lambda request: True)


def project(root, *, artifacts=None, resource=None):
    root.mkdir()
    resource = resource or mapping()
    descriptor = AttachmentDescriptor('attachments/supplier.bin', 'application/octet-stream',
        len(PAYLOAD), sha256(PAYLOAD).hexdigest())
    stat = root.stat()
    m = model([imported(), goal(2)] if artifacts is None else artifacts,
        binding=ProjectReadBinding('sample', str(root), (stat.st_dev, stat.st_ino)),
        attachments=[descriptor], resource_files=[
            ModelDocument(descriptor.path, PAYLOAD),
            ModelDocument('mappings/supplier.json', resource.source_bytes)])
    for path, raw in m.source_files.items():
        put(root, path, raw)
    (root / '.specroad/locks').mkdir(parents=True)
    put(root, 'foreign.bin', b'Unmanaged bytes stay unchanged.\x00')
    return m, resource


def resource_gate(resource):
    """Trusted fixture service for this one explicitly owned mapping resource.

    The native writer independently verifies the file bytes. This callback
    validates the fixture mapping semantics and does not grant publication.
    """
    raw = resource.source_bytes
    expected = resource.sha256
    def check(context):
        checked = ExchangeMapping(raw)
        assert checked.sha256 == expected
        return context.result()
    return ModelGate('extension:target-resources', 'synthetic-single-mapping-v1',
        lambda c: c.dependency_result({i: [] for i in c.subjects}), check,
        sha256(raw).hexdigest())


def inputs(resource):
    return dict(input_format='reqif', input_bytes=PAYLOAD, mapping_resources=[resource],
        mapping_key=resource.key, mapping_sha256=resource.sha256,
        strategy='update_if_unchanged', change_plan_id='CP-import-execution',
        request_id='import-execution-request', actor=ACTOR, planned_at=TIME,
        scope_descriptor=SCOPE, metadata_policy_version='change-metadata-v1',
        policy=POLICY, gates=[resource_gate(resource)])


def candidates():
    return [candidate(), candidate(number=1, new=True, key='external-new')]


def apply(m, values, resource, *, saved=False, options=None, **execution):
    args = inputs(resource)
    args.update(options or {})
    args['gates'] = [resource_gate(resource), *(options or {}).get('gates', ())]
    raw = prepare_import_plan(m, values, **args).canonical_bytes if saved else None
    supplied = dict(transaction_id='txn-import', authority=ALLOW, plan_bytes=raw)
    supplied.update(execution)
    return apply_import_plan(m, values, **args, **supplied)
