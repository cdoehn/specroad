"""Passive legacy transition originals and completion proof, never repair authority."""
from hashlib import sha256
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..storage.json_syntax import parse_json_object as parsed
from ._journal_codec import _transaction, journal_path
from ._schema_transition_io import read, external_backup, project_files
from .schema_transition_values import (FORMATS, TransitionJournal,
    require, request_receipt, transaction_receipt, result_object)
from ._schema_transition_proof import _backup, _verify_images, _prefix
from ._snapshot_dispatch import is_merge
from .receipt_values import transaction_receipt_path, request_receipt_path, RequestReceipt

def _archive_path(journal):
    data = journal.data
    if data['state'] == 'committed': return journal.receipt_root
    return '.specroad/recovery/transaction-audit/schema-' + sha256(data['transaction_id'].encode()).hexdigest()

def _exclude(journal, prefix):
    paths = [prefix, '.specroad/locks/project.json']
    request = journal.plan.data['request_id']
    if request is not None: paths.append(request_receipt_path(request))
    return tuple(paths)

def completion_data(journal, *, current=False):
    receipt = request_receipt(journal)
    result = result_object(journal)
    data = journal.data
    return {**result, **({'validation':data['validation'],'evidence_currently_rechecked':False}
                       if is_merge(journal.plan) else {}),
        'format_version': 'merge-transaction-v1' if is_merge(journal.plan) else 'migration-transaction-v1', 'backup': data['backup'],
        'plan_sha256': journal.plan.sha256, 'journal_sha256': journal.sha256,
        'replayed': not current, 'current_target_verified': current, 'approval_granted': False,
        'receipts': {'transaction': {'path': transaction_receipt_path(data['transaction_id']),
                                    'sha256': sha256(transaction_receipt(journal)).hexdigest()},
                     'request': None if receipt is None else {'path': receipt.path, 'sha256': receipt.sha256}}}

def find_journal(files, transaction_id):
    """One explicitly selected identity, never a scan or a data-chosen path."""
    _transaction(transaction_id)
    paths = (journal_path(transaction_id),
        transaction_receipt_path(transaction_id).rsplit('/',1)[0] + '/journal.json',
        '.specroad/recovery/transaction-audit/schema-' + sha256(transaction_id.encode()).hexdigest() + '/journal.json')
    found = [(path, raw) for path in paths if (raw := read(files, path, optional=True)) is not None]
    require(len(found) <= 1, 'transition_multiple_journal_locations')
    if not found: return None
    path, raw = found[0]
    if parsed(raw).get('format_version') not in FORMATS: return None
    journal = TransitionJournal(raw)
    data = journal.data
    require(data['transaction_id'] == transaction_id
        and data['root_identity'] == list(files.boundary._root_identity), 'transition_journal_root_binding')
    if path != paths[0]:
        require(path == _archive_path(journal) + '/journal.json'
                and data['state'] in ('committed','rolled_back'), 'transition_nonterminal_archive')
    return journal, path.rsplit('/',1)[0]

def completion_proof(files, transaction_id):
    selected = find_journal(files, transaction_id)
    require(selected is not None, 'transition_receipt_missing')
    journal, prefix = selected
    require(journal.data['state'] == 'committed' and prefix == journal.receipt_root,
            'transition_completion_unproven')
    backup = _backup(journal, read(files, prefix + '/source.zip'))
    _verify_images(files, prefix, journal, backup)
    require(read(files, prefix + '/transaction.json') == transaction_receipt(journal), 'transition_receipt_changed')
    receipt = request_receipt(journal)
    if receipt is not None:
        require(read(files, receipt.path) == receipt.source_bytes, 'transition_request_receipt_changed')
    _verify_images(files, prefix, journal, backup)
    require(find_journal(files, transaction_id) == selected, 'transition_receipt_changed')
    return journal

def historical_request(files, plan, project_id):
    identity = plan.data['request_id']
    if identity is None: return None
    raw = read(files, request_receipt_path(identity), optional=True)
    if raw is None: return None
    receipt = RequestReceipt(raw)
    require(receipt.data['project_id'] == project_id, 'transition_request_project_changed')
    selected = find_journal(files,receipt.data['transaction_id'])
    if selected is None:
        from .receipt_read import _read_confirmed_request
        from ..storage.project import ProjectSource
        checked = _read_confirmed_request(ProjectSource(files.boundary.root,
            expected_project_id=project_id),identity)
        require(checked is not None and checked.source_bytes==raw,'transition_request_receipt_changed')
        journal = None
    else:
        journal = completion_proof(files,receipt.data['transaction_id'])
        require(journal.data['project_id']==project_id
                and request_receipt(journal).source_bytes==raw,'transition_request_receipt_changed')
    # Conflict diagnostics attest a verified receipt, so prove it first even
    # when its operation hash differs. A bare JSON claim is not such proof.
    if receipt.data['operations_sha256'] != digest(plan.data['operations']):
        from .idempotency_values import RequestIdConflict
        raise RequestIdConflict(identity,receipt.data['operations_sha256'],
                                digest(plan.data['operations']),path=receipt.path)
    require(journal is not None,'transition_request_kind_mismatch')
    return completion_data(journal)

def inspect_transition(files, journal, prefix):
    data = journal.data
    backup = external_backup(files,data['backup'],plan=journal.plan)
    _backup(journal,backup.source_bytes)
    _verify_images(files,prefix,journal,backup,partial=not data['images_prepared'])
    extras = takeover_evidence(files,journal)
    actual, modes, _ = project_files(files,exclude=(*_exclude(journal,prefix),*extras))
    count = _prefix(journal,backup.files,actual)
    require(all(mode == data['source_modes'].get(p,0o644) for p,mode in modes.items()),
            'transition_file_mode_changed')
    recorded, total = data['published_count'], len(journal.plan.data['operations'][0]['changes'])
    state = data['state']
    permitted = (count == 0 if state in ('building','prepared','rolled_back') else
        count == total if state == 'committed' else
        max(0,recorded-1) <= count <= recorded if state == 'rolling_back' else recorded <= count <= min(total,recorded+1))
    require(permitted, 'transition_unproven_publication_cursor')
    return backup, count, total

def takeover_evidence(files,journal):
    """Retain exact same-transaction native ownership audit, never ignore a subtree."""
    from ._recovery_evidence import evidence_root
    from ..migration._backup_source import _scan
    data = journal.data
    prefix=evidence_root(data['transaction_id'])+'/'
    names=[p for p in _scan(files) if p.startswith(prefix)]
    if not names:return {}
    sources={r['path'] for r in journal.plan.data['operations'][0]['source_files']}
    require(not set(names)&sources,'transition_takeover_namespace_reused')
    raw={p:read(files,p) for p in names};groups={}
    for p,value in raw.items():
        relative=p[len(prefix):].split('/')
        require(len(relative)==2 and relative[0].startswith('takeover-')
                and relative[1] in ('intent.json','journal.before.json','owner.pending.json','completed.json'),
                'transition_unknown_takeover_evidence')
        groups.setdefault(relative[0],{})[relative[1]]=value
    for group in groups.values():
        require({'intent.json','journal.before.json'}<=set(group),'transition_takeover_evidence_incomplete')
        old=TransitionJournal(group['journal.before.json']);intent=parsed(group['intent.json'])
        old_data = old.data
        require(old.plan.source_bytes==journal.plan.source_bytes
            and old_data['root_identity']==data['root_identity']
            and old_data['backup']==data['backup']
            and intent.get('format_version')=='transaction-lock-takeover-v1'
            and intent.get('transaction_id')==data['transaction_id']
            and intent.get('project_id')==data['project_id']
            and intent.get('journal_sha256')==old.sha256,'transition_takeover_evidence_changed')
        if 'owner.pending.json' in group:
            require(sha256(group['owner.pending.json']).hexdigest()==intent['new_record_sha256'],
                    'transition_takeover_evidence_changed')
        if 'completed.json' in group:
            completed=parsed(group['completed.json'])
            require(completed.get('format_version')=='transaction-lock-takeover-v1'
                and completed.get('transaction_id')==data['transaction_id']
                and completed.get('journal_sha256')==old.sha256
                and completed.get('new_record_sha256')==intent['new_record_sha256']
                and completed.get('intent',{}).get('sha256')==sha256(group['intent.json']).hexdigest(),
                'transition_takeover_evidence_changed')
    return raw

def status_transition(files,journal,prefix):
    """Read-only facts; no stored success or action permission is manufactured."""
    backup,count,total=inspect_transition(files,journal,prefix)
    data, plan = journal.data, journal.plan.data
    state=data['state'];op=plan['operations'][0]
    complete=count==total and state in ('committing','committed')
    action=('complete' if complete else 'discard' if state in ('building','prepared') else 'rollback')
    return {'state':state,'transaction_id':data['transaction_id'],
        'project_id':data['project_id'],'journal_schema_validated':True,
        'base_model_root_sha256':plan['base']['model_root_sha256'],
        'target_model_root_sha256':op['target_model_root_sha256'],
        'published_count':count,'recorded_published_count':data['published_count'],
        'published_entries':[r['path'] for r in op['changes'][:count]],
        'complete_target_verified':complete,'base_verified':count==0,
        'critical_inputs_verified':True,'integrity_scope':'schema_transition_full_files',
        'critical_resources':[{'path':data['backup']['path'],
            'role':'source_backup','sha256':sha256(backup.source_bytes).hexdigest()}],
        'blockers':[],'state_actions':[],'permitted_actions':[],
        'diagnostic':'project_corrupted_manual_restore_required'}

def check_recovery_intent(name,raw,journal):
    """An immutable intention records real host authority, never a fake success."""
    from ..migration.plan_values import unb64
    value=parsed(raw)
    require(set(value)=={'format_version','request','journal_before_base64','authority_id','authority_version'}
        and value['format_version']=='schema-transition-recovery-intent-v1'
        and name=='recovery-'+sha256(raw).hexdigest()+'.json' and raw==jcs(value)
        and all(type(value[k]) is str and bool(value[k]) for k in ('authority_id','authority_version')),
        'transition_recovery_intent_changed')
    old=TransitionJournal(unb64(value['journal_before_base64']))
    data = journal.data
    require({k:v for k,v in old.data.items() if k not in ('state','published_count')} ==
            {k:v for k,v in data.items() if k not in ('state','published_count')},
            'transition_recovery_intent_binding')
    request=value['request']
    require(type(request) is dict and set(request)=={'action','transaction_id','project_id',
        'journal_sha256','plan_sha256','backup','root_identity','actor','reason'}
        and request['action'] in ('discard','rollback','complete')
        and request['transaction_id']==data['transaction_id']
        and request['project_id']==data['project_id']
        and request['journal_sha256']==old.sha256 and request['plan_sha256']==journal.plan.sha256
        and request['backup']==data['backup'] and request['root_identity']==data['root_identity'],
        'transition_recovery_intent_binding')
