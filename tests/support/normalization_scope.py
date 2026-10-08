"""Complete owned format-scope fixtures, not production resource approvers."""
from contextlib import contextmanager
from pathlib import Path
from specroad.changes import (prepare_format_target, prepare_publication_check,
    project_lock, begin_building_journal, stage_building_journal)
from specroad.model.canonical import canonical_json_bytes
from specroad.model.model_manifest import ProjectReadBinding
from specroad.validation import ModelDocument
from .targets import model, POLICY, gate
from .normalization import FIELDS
from .publication import options, ALLOW, TRANSACTION
from .folds import goal

# The resource semantics service is an explicit test host, never a default
# approval in production. Missing/denied service behavior has separate tests.
GATES = (gate('extension:target-resources'),)


def prepared(root, *, artifacts=None, config=None, select=None, gates=GATES):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    info = root.stat()
    resources = [ModelDocument('rules/sample.json', canonical_json_bytes({
        'schema_version': '0.2.0', 'rule_id': 'sample', 'version': '1.0.0'})),
        ModelDocument('mappings/sample.json', canonical_json_bytes({
        'schema_version': '0.2.0', 'mapping_id': 'sample', 'version': '1.0.0'}))]
    value = model(artifacts if artifacts is not None else [goal()], config=config,
        resource_files=resources,
        binding=ProjectReadBinding('sample', str(root), (info.st_dev, info.st_ino)))
    for path, raw in value.source_files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    assessment = prepare_format_target(value, policy=POLICY, gates=gates, **FIELDS)
    plan = assessment.plan
    if select is not None:
        from .targets import resign
        plan = resign(plan, lambda data: data.update(operations=[op for op in data['operations']
                                                               if op['path'] in select]))
    check = prepare_publication_check(plan, value, policy=POLICY, gates=gates)
    return value, plan, check


@contextmanager
def staged(root, *, gates=GATES, **kwargs):
    value, plan, check = prepared(root, gates=gates, **kwargs)
    with project_lock(root, **options(check)) as held:
        building = begin_building_journal(check, held_lock=held, transaction_id=TRANSACTION,
                                          authority=ALLOW, gates=gates)
        journal = stage_building_journal(check, building, held_lock=held,
                                        authority=ALLOW, gates=gates)
        yield value, plan, check, held, journal
