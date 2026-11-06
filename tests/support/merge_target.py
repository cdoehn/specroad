"""Complete native synthetic projects; no success callbacks or invented history."""
from copy import deepcopy
import json

from specroad.merge import build_merge_conflicts, prepare_merge_metadata, prepare_merge_target
from specroad.model.canonical import canonical_json_bytes as jcs
from support.domain import domain_value
from support.inspection import inspection_project
from support.records import record_value
from support.merge_relations import history_for
from support.merge_resolution import PLAN_ID
from test_merge_inventory import bind_files


def seed(root, *, values=None, profiles=(), fail_on='error'):
    model = inspection_project(root, artifacts=values if values is not None else
        [record_value('document'), domain_value('goal')], extra_profiles=profiles)
    files = model.source_files
    config = json.loads(files['specroad.json'])
    config['validation_policy']['fail_on'] = fail_on
    files['specroad.json'] = jcs(config)
    return files


def replace(files, kind, *, identifier=None, **changes):
    files = dict(files)
    path = next(p for p, raw in files.items() if p.startswith('spec/') and
        json.loads(raw)['artifact_type'] == kind and
        (identifier is None or json.loads(raw)['id'] == identifier))
    value = deepcopy(json.loads(files[path])); value.update(changes)
    files[path] = jcs(value)
    return files


def inputs(root, variants):
    root.mkdir()
    sources = bind_files(root, variants)
    history = history_for(sources)
    plan = build_merge_conflicts(sources, plan_id=PLAN_ID, history=history)
    metadata = prepare_merge_metadata(plan.canonical_bytes, sources, history=history,
                                     expected_plan_sha256=plan.sha256)
    return sources, history, plan, metadata


def target(values, *, services=None):
    sources, history, plan, metadata = values
    return prepare_merge_target(metadata.canonical_bytes, plan.canonical_bytes, sources,
        history=history, expected_metadata_sha256=metadata.sha256,
        expected_plan_sha256=plan.sha256, services=services)
