"""Native proof and explicit recovery for the shared schema-transition branch."""
from hashlib import sha256
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..storage.json_syntax import parse_json_object as parsed
from ._journal_codec import _transaction, _hash, journal_path
from ._schema_transition_io import read, external_backup, project_files
from .schema_transition_values import (FORMAT, TransitionJournal, SchemaTransitionError,
    require, request_receipt, transaction_receipt)
from .schema_transition import (_backup, _verify_images, _prefix, _Session, _held,
    _exclude, completion_data, _archive_path)
from .recovery_values import RecoveryAuthority, RecoveryObservation
from .receipt_values import transaction_receipt_path, request_receipt_path, RequestReceipt
from ._lock_files import LockFiles


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
    if parsed(raw).get('format_version') != FORMAT: return None
    journal = TransitionJournal(raw)
    require(journal.data['transaction_id'] == transaction_id
        and journal.data['root_identity'] == list(files.boundary._root_identity), 'transition_journal_root_binding')
    if path != paths[0]:
        require(path == _archive_path(journal) + '/journal.json'
                and journal.data['state'] in ('committed','rolled_back'), 'transition_nonterminal_archive')
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
    backup = external_backup(files,journal.data['backup'])
    _backup(journal,backup.source_bytes)
    _verify_images(files,prefix,journal,backup,partial=not journal.data['images_prepared'])
    extras = takeover_evidence(files,journal)
    actual, modes, _ = project_files(files,exclude=(*_exclude(journal,prefix),*extras))
    count = _prefix(journal,backup.files,actual)
    require(all(mode == journal.data['source_modes'].get(p,0o644) for p,mode in modes.items()),
            'transition_file_mode_changed')
    recorded, total = journal.data['published_count'], len(journal.plan.data['operations'][0]['changes'])
    state = journal.data['state']
    permitted = (count == 0 if state in ('building','prepared','rolled_back') else
        count == total if state == 'committed' else
        max(0,recorded-1) <= count <= recorded if state == 'rolling_back' else recorded <= count <= min(total,recorded+1))
    require(permitted, 'transition_unproven_publication_cursor')
    return backup, count, total


def _recover_transition(transaction_id, *, held_lock, authority, expected_journal_sha256, action, actor=None, reason=None):
    """No forward retries. Complete a proven full target, otherwise restore base."""
    require(type(authority) is RecoveryAuthority and _hash(expected_journal_sha256)
            and action in ('complete','rollback','discard'), 'transition_recovery_inputs_required', exit_code=7)
    from .locking import HeldProjectLock
    require(type(held_lock) is HeldProjectLock,
            'transition_recovery_lock_required',exit_code=7)
    held_lock.check(); files = held_lock._files
    selected = find_journal(files, transaction_id)
    require(selected is not None, 'transition_journal_missing')
    journal, prefix = selected
    _held(held_lock, journal)
    require(held_lock.record.data['kind'] == 'recovery', 'transition_recovery_lock_required', exit_code=7)
    require(journal.sha256 == expected_journal_sha256, 'transition_journal_changed')
    request = {'action': action, 'transaction_id': transaction_id, 'project_id': journal.data['project_id'],
        'journal_sha256': journal.sha256, 'plan_sha256': journal.plan.sha256,
        'backup': journal.data['backup'], 'root_identity': journal.data['root_identity'],
        'actor': actor, 'reason': reason}
    bound = jcs(request)
    allowed = authority.check(request)
    require(type(allowed) is bool and allowed and jcs(request) == bound, 'transition_recovery_not_authorized', exit_code=7)
    require(find_journal(files,transaction_id) == selected, 'transition_journal_changed')
    if prefix == journal.receipt_root:
        require(action == 'complete', 'transition_committed_requires_completion')
        checked = completion_proof(files,transaction_id)
        return RecoveryObservation._create({**completion_data(checked), 'cleanup_completed':True,
            'recovery_completed':True, 'normative_writes_by_recovery':0})
    # The current kernel owner may have just written its native takeover audit.
    extras = takeover_evidence(files, journal)
    backup = external_backup(files,journal.data['backup'])
    _backup(journal,backup.source_bytes)
    _verify_images(files,prefix,journal,backup,partial=not journal.data['images_prepared'])
    actual = project_files(files,exclude=(*_exclude(journal,prefix),*extras))[0]
    count = _prefix(journal,backup.files,actual)
    total = len(journal.plan.data['operations'][0]['changes']); recorded = journal.data['published_count']
    state = journal.data['state']
    if state in ('building','prepared','rolled_back'): require(count==0,'transition_unproven_publication_cursor')
    elif state=='rolling_back':require(max(0,recorded-1)<=count<=recorded,'transition_unproven_publication_cursor')
    elif state=='committed':require(count==total,'transition_unproven_publication_cursor')
    else:require(recorded<=count<=min(total,recorded+1),'transition_unproven_publication_cursor')
    if action=='complete':require(count==total and state in ('committing','committed'),'transition_complete_target_required')
    else:
        require(state!='committed' and (count<total or state=='rolling_back'), 'transition_full_target_requires_completion')
        if action=='discard':require(count==0 and state in ('building','prepared','rolled_back'),'transition_discard_published')
    require(all(mode == journal.data['source_modes'].get(p,0o644) for p,mode in
                project_files(files,exclude=(*_exclude(journal,prefix),*extras))[1].items()),
            'transition_file_mode_changed')
    if prefix != journal.path.rsplit('/',1)[0]:
        require(not files.journal_entries(),'transition_active_set_changed')
        require(state=='rolled_back' and count==0,'transition_terminal_mismatch')
        return RecoveryObservation._create({'state':'rolled_back','recovery_completed':True,
            'cleanup_completed':True,'current_source_verified':True,'normative_writes_by_recovery':0,
            'write_authorized':False,'approval_granted':False})
    session=_Session(held_lock,journal,backup,recover=True)
    session.extra_evidence=extras
    session.live_count=count
    session.guard()
    intent = jcs({'format_version':'schema-transition-recovery-intent-v1',
        'request':parsed(bound), 'journal_before_base64':__import__('base64').b64encode(journal.source_bytes).decode('ascii'),
        'authority_id':authority.authority_id,'authority_version':authority.version})
    name='recovery-'+sha256(intent).hexdigest()+'.json'
    check_recovery_intent(name,intent,journal)
    from ._schema_transition_io import complete_owned_image
    complete_owned_image(files,session.prefix+'/'+name,intent,guard=session.guard)
    session.guard()
    writes=0
    if action=='complete':
        if state!='committed':session.save('committed',total)
    else:
        if state not in ('rolling_back','rolled_back'):session.save('rolling_back',count)
        elif state=='rolling_back' and recorded!=count:session.save('rolling_back',count)
        for index in reversed(range(count)):
            session.effect(index,rollback=True);writes+=1
        if session.journal.data['state']!='rolled_back':session.save('rolled_back',0)
    session.finish()
    if action=='complete':
        return RecoveryObservation._create({**completion_data(session.journal,current=True),
            'cleanup_completed':True,'recovery_completed':True,'normative_writes_by_recovery':0})
    return RecoveryObservation._create({'state':'rolled_back','journal_sha256':session.journal.sha256,
        'transaction_id':transaction_id,'current_source_verified':True,'recovery_completed':True,
        'cleanup_completed':True,'normative_writes_by_recovery':writes,
        'write_authorized':False,'approval_granted':False})


def takeover_evidence(files,journal):
    """Retain exact same-transaction native ownership audit, never ignore a subtree."""
    from ._recovery_evidence import evidence_root
    from ..migration._backup_source import _scan
    prefix=evidence_root(journal.data['transaction_id'])+'/'
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
        require(old.plan.source_bytes==journal.plan.source_bytes
            and old.data['root_identity']==journal.data['root_identity']
            and old.data['backup']==journal.data['backup']
            and intent.get('format_version')=='transaction-lock-takeover-v1'
            and intent.get('transaction_id')==journal.data['transaction_id']
            and intent.get('project_id')==journal.data['project_id']
            and intent.get('journal_sha256')==old.sha256,'transition_takeover_evidence_changed')
        if 'owner.pending.json' in group:
            require(sha256(group['owner.pending.json']).hexdigest()==intent['new_record_sha256'],
                    'transition_takeover_evidence_changed')
        if 'completed.json' in group:
            completed=parsed(group['completed.json'])
            require(completed.get('format_version')=='transaction-lock-takeover-v1'
                and completed.get('transaction_id')==journal.data['transaction_id']
                and completed.get('journal_sha256')==old.sha256
                and completed.get('new_record_sha256')==intent['new_record_sha256']
                and completed.get('intent',{}).get('sha256')==sha256(group['intent.json']).hexdigest(),
                'transition_takeover_evidence_changed')
    return raw


def status_transition(files,journal,prefix):
    """Read-only facts; no stored success or action permission is manufactured."""
    backup,count,total=inspect_transition(files,journal,prefix)
    state=journal.data['state'];op=journal.plan.data['operations'][0]
    complete=count==total and state in ('committing','committed')
    action=('complete' if complete else 'discard' if state in ('building','prepared') else 'rollback')
    return {'state':state,'transaction_id':journal.data['transaction_id'],
        'project_id':journal.data['project_id'],'journal_schema_validated':True,
        'base_model_root_sha256':journal.plan.data['base']['model_root_sha256'],
        'target_model_root_sha256':op['target_model_root_sha256'],
        'published_count':count,'recorded_published_count':journal.data['published_count'],
        'published_entries':[r['path'] for r in op['changes'][:count]],
        'complete_target_verified':complete,'base_verified':count==0,
        'critical_inputs_verified':True,'integrity_scope':'schema_transition_full_files',
        'critical_resources':[{'path':journal.data['backup']['path'],
            'role':'source_backup','sha256':sha256(backup.source_bytes).hexdigest()}],
        'blockers':[],'state_actions':[action],'permitted_actions':[],
        'diagnostic':'explicit_schema_transition_recovery_required'}


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
    require({k:v for k,v in old.data.items() if k not in ('state','published_count')} ==
            {k:v for k,v in journal.data.items() if k not in ('state','published_count')},
            'transition_recovery_intent_binding')
    request=value['request']
    require(type(request) is dict and set(request)=={'action','transaction_id','project_id',
        'journal_sha256','plan_sha256','backup','root_identity','actor','reason'}
        and request['action'] in ('discard','rollback','complete')
        and request['transaction_id']==journal.data['transaction_id']
        and request['project_id']==journal.data['project_id']
        and request['journal_sha256']==old.sha256 and request['plan_sha256']==journal.plan.sha256
        and request['backup']==journal.data['backup'] and request['root_identity']==journal.data['root_identity'],
        'transition_recovery_intent_binding')


def recover_transition(transaction_id, **options):
    """Preserve uncertainty from interrupted recovery, including lower I/O errors."""
    try:
        return _recover_transition(transaction_id,**options)
    except Exception as error:
        from .recovery_values import RecoveryError
        raise RecoveryError(getattr(error,'reason','schema_transition_recovery_interrupted'),
            exit_code=getattr(error,'exit_code',6),mutation_possible=True) from error
