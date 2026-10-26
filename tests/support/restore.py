"""Native synthetic full projects and original snapshots, never release proof."""
from specroad.archive.project_snapshot import build_project_baseline_manifest
from specroad.bundles import prepare_project_bundle
from specroad.model.canonical import canonical_json_bytes
from specroad.model.paths import artifact_path
from specroad.recovery import prepare_restore_plan
from .domain import domain_value
from .inspection import inspection_project
from .model import put
from .records import record_value, ref


def restore_case(tmp_path, kind='project_bundle', *, baseline_kind='working', values=None):
    origin, current = tmp_path / 'origin', tmp_path / 'current'
    model = inspection_project(origin, artifacts=values if values is not None else
                               [record_value('document'), domain_value('goal')])
    current.mkdir()
    files = model.source_files
    for path, raw in files.items():
        put(current, path, raw)
    if kind == 'project_bundle':
        raw = prepare_project_bundle(origin).source_bytes
        path = 'project.zip'
        extra = {}
    else:
        snapshot = build_project_baseline_manifest(model, baseline_id=ref('BASE'))
        record = record_value('baseline', baseline_kind=baseline_kind, **{key: snapshot.data[key]
            for key in ('scope_descriptor', 'manifest', 'model_root_sha256', 'configuration_hash', 'profiles', 'tool_version')})
        raw = canonical_json_bytes(record)
        path = artifact_path('baseline', record['id'], 'SR')
        for item in snapshot.objects:
            put(origin, item.reference.path, item.content)
        extra = {'default_locale': 'en-GB', 'generated_path': 'output'}
    put(origin, path, raw)
    options = {'project_root': current, 'source_root': origin, 'source_path': path,
               'source_kind': kind, **extra}
    return options, files, raw


def plan_for(options):
    return prepare_restore_plan(**options)
