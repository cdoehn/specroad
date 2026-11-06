"""Native synthetic projects and explicit host authority for merge publication."""
from pathlib import Path
from specroad.merge import plan_merge_publication,create_merge_backup,apply_merge_publication
from specroad.changes.publication_values import PublicationAuthority
from support.merge_target import seed,replace,inputs,target
from support.merge_resolution import ACTOR,WHEN


def setup(tmp_path, *, variants=None, services=None, fields=None):
    if variants is None:
        files=seed(tmp_path/'seed')
        ours=replace(files,'goal',title='Ours title')
        theirs=replace(files,'goal',statement='Theirs statement')
        variants=[files,ours,theirs]
    values=inputs(tmp_path/'inputs',variants)
    observation=target(values,services=services)
    assert observation.target_validated, observation.data
    sources,history,original,metadata=values
    root=Path(sources.ours.source_root)
    options=dict(history=history,expected_target_sha256=observation.sha256,
        expected_metadata_sha256=metadata.sha256,expected_plan_sha256=original.sha256,
        change_plan_id='synthetic-merge-publication',actor=ACTOR,planned_at=WHEN,
        request_id='synthetic-merge-request',services=services)
    options.update(fields or {})
    plan=plan_merge_publication(root,observation.canonical_bytes,metadata.canonical_bytes,
        original.canonical_bytes,sources,**options)
    external=tmp_path/'backups';external.mkdir()
    backup=create_merge_backup(root,plan.source_bytes,expected_plan_sha256=plan.sha256,
        output='before.zip',output_root=external)
    args={'expected_plan_sha256':plan.sha256,'sources':sources,'transaction_id':'synthetic-merge-transaction',
        'backup_descriptor':{'path':backup['file']['path'],'output_root':str(external),
            'size':backup['file']['size'],'sha256':backup['file']['sha256'],
            'source_files_sha256':backup['source_files_sha256']},
        'authority':PublicationAuthority('synthetic-merge-host','1',lambda request:True),'services':services}
    return root,plan,args,observation


def apply(root,plan,args):
    return apply_merge_publication(root,plan.source_bytes,**args)


def tree(root):
    return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}


def normative(root):
    return {p:b for p,b in tree(root).items() if not p.startswith('.specroad/')}
