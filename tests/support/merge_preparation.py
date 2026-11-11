"""Small native inputs; each case owns its sources and mutable Work directory."""
from base64 import b64decode
from pathlib import Path

from specroad.bundles import prepare_project_bundle
from specroad.changes import ChangePlan
from specroad.cli.commands import builtin_registry
from specroad.documents._structure_graph import _document_structure
from specroad.graph.references import RelationReferences
from specroad.merge import SourceRequest, SourceSnapshot, load_merge_sources
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.paths import artifact_path
from specroad.work.merge import prepare_merge_work, resume_merge_work, merge_work_result
from specroad.work.root import WorkDirectory
from specroad.work.checkpoints import CheckpointStore
from specroad.security import ProjectBoundary
from specroad.validation import ModelGate
from specroad.validation._document_roles import _document_roles
from support.git_objects import GitFixture
from support.model import put
from support.merge_relations import history_for
from support.merge_resolution import PLAN_ID
from support.domain import domain_value
from support.inspection import inspection_project
from support.languages import small_restore_registry
from support.records import record_value
from test_baseline_creation import preview


def baseline_document_gate(model):
    """Register real native document/section checks for this small host fixture.

    Check the proposed context, including all dependencies; do not substitute
    an earlier observation or claim block/view semantics for this fixture.
    """
    def dependencies(context):
        return context.dependency_result({identity: list(context.all_ids) for identity in context.subjects})

    def check(context):
        if any(context.artifact(identity)['artifact_type'] not in ('document', 'section')
               for identity in context.subjects):
            return context.result([{'reason': 'merge_fixture_document_specialist_required', 'severity': 'error'}])
        records = context.source_records
        _, _, roles = _document_roles((record.path, record.data) for record in records)
        _, _, _, structure = _document_structure(records, RelationReferences(records),
            {record.identity.id: record.data for record in records})
        return context.result([*roles, *structure])

    return ModelGate('document_model', 'synthetic-merge-native-documents-v1',
                     dependencies, check, model._sources_sha256)


def baseline_template(root, *, values=None):
    # Full-project merge validation requires a primary document. Bind it into
    # the native Baseline before deriving equivalent inputs for every adapter.
    model = inspection_project(root, artifacts=[record_value('document'), domain_value('goal')] if values is None else values,
                               language_registry=small_restore_registry())
    prepared = preview(model, gates=(baseline_document_gate(model),))
    assert prepared['target_validated'], prepared['diagnostics']
    operation = ChangePlan(jcs(prepared['plan'])).data['operations'][0]
    record = operation['record']
    put(root, artifact_path('baseline', record['id'], 'SR'), jcs(record))
    for row in operation['objects']:
        put(root, row['path'], b64decode(row['bytes_base64']))
    snapshot = SourceSnapshot(SourceRequest(root, 'baseline', record['id']))
    archive = {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob('*') if path.is_file()}
    return snapshot.files, archive, record['id']


def adapter_case(root, template, kind):
    files, archive, baseline_id = template
    local = root/'local'
    local.mkdir(parents=True)
    for path, raw in files.items():
        put(local, path, raw)
    if kind == 'local':
        request = SourceRequest(local)
    elif kind == 'git':
        git = GitFixture(root/'git')
        request = SourceRequest(git.root, 'git', git.commit(files))
    elif kind == 'baseline':
        origin = root/'archive'; origin.mkdir()
        for path, raw in archive.items():
            put(origin, path, raw)
        request = SourceRequest(origin, 'baseline', baseline_id)
    else:
        bundle = root/'project.zip'
        bundle.write_bytes(prepare_project_bundle(local).source_bytes)
        request = SourceRequest(bundle, 'bundle')
    sources = load_merge_sources(request, request, request)
    return sources, history_for(sources), request


def store_for(root, sources, history, **options):
    initial = prepare_merge_work(builtin_registry(), sources, plan_id=PLAN_ID, history=history, **options)
    paths = dict.fromkeys(Path(source.source_root).parent if source.kind == 'bundle'
                          else Path(source.source_root) for source in
                          (sources.base, sources.ours, sources.theirs))
    protected = tuple(ProjectBoundary(path) for path in paths)
    store = CheckpointStore(WorkDirectory(initial, protected_roots=protected, directory=root), initial)
    store.publish(initial)
    return store


def finish(store, window):
    current = store.read()
    remaining = len(current.entries('remaining'))
    for _ in range(remaining+2):
        before = current.as_dict()
        current = resume_merge_work(store, max_units=window)
        after = current.as_dict()
        if after['state'] == 'completed':
            return merge_work_result(store)
        assert after['progress']['completed_units'] > before['progress']['completed_units']
    raise AssertionError('Finite native merge preparation failed to complete')


def example_inputs(root, command):
    root.mkdir(parents=True, exist_ok=True)
    template = baseline_template(root/'seed')
    _, history, request = adapter_case(root/'sources', template, 'local')
    path = root/'history.json'; path.write_bytes(jcs(history))
    options = {'--history': str(path), '--plan-id': PLAN_ID, '--format': 'json'}
    options.update({'--'+role: str(request.root) for role in ('base', 'ours', 'theirs')})
    return {'command_id': command.command_id, 'options': options}
