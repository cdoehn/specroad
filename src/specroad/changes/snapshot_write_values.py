"""Closed passive snapshot audit binding for the normal guarded writer."""
from ..migration.plan_values import b64, unb64, source_path, safe_path
from ..model.canonical import canonical_json_sha256 as digest
from ..model.configuration import ProjectConfiguration
from ..storage.json_syntax import parse_json_object as parsed
from .values import ChangePlan
from .schema_transition_values import require, authoring
from ._snapshot_dispatch import command_for, is_merge

FORMAT = 'snapshot-write-validation-v1'


def validation(plan, backup, qualification):
    return dict(format_version=FORMAT, plan_bytes_base64=b64(plan.source_bytes),
                backup=backup, qualification=qualification,
                native=qualification['native'] if is_merge(plan) else qualification)


def checked_plan(value):
    require(type(value) is dict and set(value) == {'format_version','plan_bytes_base64',
        'backup','qualification','native'} and value['format_version'] == FORMAT,
        'snapshot_write_validation_schema')
    plan = ChangePlan(unb64(value['plan_bytes_base64']))
    authoring(plan)
    require(plan.data['metadata_policy_version'] in ('migration-metadata-v1','merge-metadata-v1'),
            'snapshot_write_policy')
    backup = value['backup'];op = plan.data['operations'][0]
    from pathlib import Path
    from ._journal_codec import _hash
    require(type(backup) is dict and set(backup) == {'path','output_root','size','sha256','source_files_sha256'}
        and type(backup['size']) is int and backup['size'] > 0 and _hash(backup['sha256'])
        and backup['source_files_sha256'] == digest(op['source_files'])
        and all(type(backup[k]) is str and Path(backup[k]).is_absolute()
            and str(Path(backup[k])) == backup[k] and '..' not in Path(backup[k]).parts
            for k in ('path','output_root'))
        and Path(backup['path']).is_relative_to(backup['output_root']), 'snapshot_write_backup_binding')
    qualification = value['qualification']
    if is_merge(plan):
        require(type(qualification) is dict and set(qualification) == {'format_version','native',
            'assessment','relation_reviews','evidence','code_references'}
            and qualification['format_version'] == 'merge-publication-validation-v1'
            and all(type(qualification[k]) is list for k in ('relation_reviews','evidence','code_references')),
            'snapshot_write_merge_qualification')
        require(value['native'] == qualification['native'], 'snapshot_write_qualification_binding')
    else:
        require(value['native'] == qualification, 'snapshot_write_qualification_binding')
    return plan


def effect_path(plan, path):
    """Keep normal path restrictions; only the bound native registry is additional."""
    from .write_guard_values import _path
    op = plan.data['operations'][0]
    config = ProjectConfiguration(parsed(unb64(op['inputs']['target_configuration']))).data
    registry = config.get('language_registry', {}).get('path')
    if path == registry:
        safe_path(path)
    else:
        _path(path)
    require(path in {r['path'] for r in op['changes']}, 'snapshot_unplanned_effect', exit_code=7)


def check_write(write):
    """A normal receipt must bind the complete actual snapshot, not only flags."""
    plan = checked_plan(write['validation']);data=plan.data;marker=write['marker'];op=data['operations'][0]
    require(marker['command_id'] == command_for(plan) and marker['plan_sha256'] == plan.sha256
        and marker['request_id'] == data['request_id']
        and marker['base_model_root_sha256'] == data['base']['model_root_sha256']
        and marker['target_model_root_sha256'] == data['expected_result']['model_root_sha256']
        and write['actor'] == data['actor'] and write['planned_at'] == data['planned_at']
        and write['change_plan_id'] == data['change_plan_id'] and write['operations'] == data['operations'],
        'snapshot_write_plan_binding')
    target_config=parsed(unb64(op['inputs']['target_configuration']))
    require(marker['project_id'] == target_config['project_id'], 'snapshot_write_project_binding')
    before={r['path']:{k:r[k] for k in ('size','sha256')} for r in op['source_files']}
    after={r['path']:{k:r[k] for k in ('size','sha256')} for r in op['target_files']}
    require(write['target_inventory'] == op['target_files'], 'snapshot_write_target_binding')
    expected=[dict(path=p,before=before.get(p),after=after.get(p)) for p in sorted(before.keys()|after.keys())
              if before.get(p)!=after.get(p)]
    require(write['files'] == expected, 'snapshot_write_effect_binding')
    for p in before.keys()|after.keys():source_path(p)
    for row in expected:effect_path(plan,row['path'])
    require(all(before.get(p) == after.get(p) for p in op.get('protected_paths', [])),
            'snapshot_write_protected_file_changed', exit_code=7)
    return plan


def result(write, *, current=False, evidence_current=False):
    from .write_guard_values import completion
    plan=check_write(write);done=completion(write,current=current).data
    data=dict(**done['result_object'],format_version='merge-transaction-v2' if is_merge(plan)
        else 'migration-transaction-v2',backup=write['validation']['backup'],plan_sha256=plan.sha256,
        write_sha256=digest(write),replayed=not current,current_target_verified=current,
        approval_granted=False,receipts=done['receipts'])
    if is_merge(plan):
        data.update(validation=write['validation']['qualification'],evidence_currently_rechecked=evidence_current)
    return data
