"""Bind every file entry to independent checked before/after bytes."""
from hashlib import sha256
from ..model.canonical import canonical_json_bytes
from .publication_values import PublicationPreflight
from .journal_values import BuildingJournal,JournalError,JOURNAL_VERSION
from ._journal_codec import _transaction
from ._discard_basis_contract import discard_basis_descriptor

def prepare_building_journal(preflight, *, transaction_id):
    """Pure complete file inventory derived from the checked publication request.

    Only the current adapter's changed artifact bytes are supported. No phantom
    entries for unchanged sources; no assumed delete or specialized operations.
    No live reads, no staging, no time/identity generation and no write permission.
    """
    if type(preflight) is not PublicationPreflight:
        raise JournalError('publication_preflight_required', exit_code=2)
    transaction_id = _transaction(transaction_id)
    request = preflight.request
    model, p = preflight._model, request.plan
    data, pv = request.data, p.data
    old = model.source_files
    documents = sorted(request.documents, key=lambda d:d.path.encode('utf-8'))
    if len({d.path for d in documents}) != len(documents) or set(data['changed_paths']) != {d.path for d in documents}:
        raise JournalError('publication_inventory_mismatch')
    target = {item['path']:item['sha256'] for item in data['target_files']}
    expected_target = {**model.source_files, **{d.path:d.content for d in request.documents},
                       **{d.path:d.content for d in preflight._package_files}}
    target_inventory = [{'path':path, 'size':len(raw), 'sha256':sha256(raw).hexdigest()}
                        for path, raw in sorted(expected_target.items())]
    entries=[]; prefix='.specroad/transactions/'+transaction_id
    for i,d in enumerate(documents):
        before = old.get(d.path)
        if d.path not in target or target[d.path] != sha256(d.content).hexdigest() or before == d.content:
            raise JournalError('publication_target_binding_mismatch')
        entries.append({'path':d.path, 'existed_before':before is not None,
            'before_sha256':None if before is None else sha256(before).hexdigest(),
            'before_size':None if before is None else len(before),
            'after_sha256':sha256(d.content).hexdigest(),'after_size':len(d.content),
            'staging_path':prefix+'/staging/'+str(i)+'.bin',
            'before_image_path':None if before is None else prefix+'/before/'+str(i)+'.bin',
            'published':False})
    value={'format_version':JOURNAL_VERSION,'state':'building','transaction_id':transaction_id,
           'project_id':model.binding.project_id,'root_identity':list(model.binding.root_identity),
           'change_plan_id':pv['change_plan_id'],'request_id':pv['request_id'],
           'actor':pv['actor'],'planned_at':pv['planned_at'],'plan_sha256':p.sha256,
           'plan_bytes_sha256':sha256(p.source_bytes).hexdigest(),'request_sha256':request.sha256,
           'authoring_binding':data['authoring_binding'],
           'authoring_sha256':data['authoring_sha256'],
           'base_model_root_sha256':pv['base']['model_root_sha256'],
           'target_model_root_sha256':data['target_root_sha256'],
           'discard_basis':discard_basis_descriptor(preflight),
           'target_inventory':target_inventory,
           'files':entries,'published_count':0}
    return BuildingJournal(canonical_json_bytes(value))


def verify_building_journal(journal, preflight):
    """Bind the entire inventory to independent plan/source/target observations."""
    if type(journal) is not BuildingJournal:
        raise JournalError('building_journal_required', exit_code=2)
    expected = prepare_building_journal(preflight,transaction_id=journal.data['transaction_id'])
    value = expected.data
    if 'discard_basis' not in journal.data:
        value.pop('discard_basis')
    if canonical_json_bytes(journal.data) != canonical_json_bytes(value):
        raise JournalError('journal_plan_inventory_mismatch',exit_code=6,path=journal.path)
    return None

