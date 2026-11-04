"""Apply-only synthetic migrated source states, without migration execution grants."""
from specroad.migration.planning import plan_migration
from .migration_plans import FIELDS, mapped_inputs, planned_files
from .migration_relations import immutable_source

MANIFEST = 'mappings/legacy-manifest.json'
BASELINE = 'spec/baselines/SR-BASE-0001.json'
PROJECT_ID = 'synthetic-reference-project'


def migrated(files=None):
    files = immutable_source() if files is None else files
    plan = plan_migration(files, inputs=mapped_inputs(files), **FIELDS).change_plan
    return files, planned_files(files, plan), plan


def write_files(root, files):
    for path, raw in files.items():
        target = root/path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
