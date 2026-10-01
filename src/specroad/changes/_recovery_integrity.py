"""Read-only proof of necessary recovery bytes, not a recovery write grant."""
from ._recovery_rollback import _fingerprint
from .execution_values import ChangeExecutionError
from ..security import SafetyViolation


def inspect_critical_inputs(files, journal):
    """Keep missing evidence visible without guessing bytes or a terminal state.

    Prepared promises complete images. Building may still be writing them.
    A consumed stage is not missing input when the target is already complete;
    otherwise rollback only needs a before image for a live changed target.
    """
    data = journal.data
    state = data['state']
    resources, blockers, tokens = [], [], {}

    def observe(path):
        if path not in tokens:
            try:
                tokens[path] = _fingerprint(files, path)
            except (ChangeExecutionError, SafetyViolation, OSError) as error:
                tokens[path] = {'error': getattr(error, 'reason', 'recovery_input_unreadable')}
        return tokens[path]

    def exact(token, size, digest):
        return (token is not None and 'error' not in token
                and (token['size'], token['sha256']) == (size, digest))

    def image(path, role, size, digest, required, *, partial=False):
        token = observe(path)
        record = {'path': path, 'role': role, 'recovery_critical': True,
                  'required': required, 'expected_size': size,
                  'expected_sha256': digest, 'observed_size': None,
                  'observed_sha256': None, 'status': 'unavailable'}
        if token is None:
            record['status'] = 'missing'
        elif 'error' in token:
            record['reason'] = token['error']
        else:
            record.update(observed_size=token['size'], observed_sha256=token['sha256'])
            record['status'] = ('verified' if exact(token, size, digest) else
                'partial_unverified' if partial and token['size'] < size else 'mismatch')
        resources.append(record)
        if ((required and record['status'] != 'verified') or
                (partial and record['status'] in ('mismatch', 'unavailable'))):
            blockers.append({'path': path, 'role': role,
                             'reason': 'recovery_' + role + '_' + record['status']})
        return record

    complete_target = False
    live = {}
    if state in ('committing', 'rolling_back', 'committed', 'rolled_back'):
        live = {item['path']: observe(item['path']) for item in data['target_inventory']}
        complete_target = all(exact(live[item['path']], item['size'], item['sha256'])
                              for item in data['target_inventory'])
        changed = {entry['path']: entry for entry in data['files']}
        for item in data['target_inventory']:
            entry = changed.get(item['path'])
            token = live[item['path']]
            if entry is None or state == 'committed':
                image(item['path'], 'target', item['size'], item['sha256'], True)
                continue
            is_base = (token is None if not entry['existed_before'] else
                       exact(token, entry['before_size'], entry['before_sha256']))
            is_target = exact(token, entry['after_size'], entry['after_sha256'])
            if not is_base and (not is_target or state == 'rolled_back'):
                blockers.append({'path': entry['path'], 'role': 'target',
                                 'reason': 'recovery_target_not_proven_base_or_target'})

    for entry in data['files']:
        before_required = state == 'prepared'
        if state in ('committing', 'rolling_back') and not complete_target:
            before_required = exact(live.get(entry['path']), entry['after_size'], entry['after_sha256'])
        if entry['before_image_path'] is not None:
            image(entry['before_image_path'], 'before_image', entry['before_size'],
                  entry['before_sha256'], before_required, partial=state == 'building')
        image(entry['staging_path'], 'staging', entry['after_size'], entry['after_sha256'],
              state == 'prepared', partial=state == 'building')

    if state == 'committed':
        # Hash-consistent claims do not replace the journal-bound receipt contract.
        from .receipt_projection import prepare_recovery_receipts
        transaction, request, expected = prepare_recovery_receipts(journal.predecessor)
        if expected.source_bytes != journal.source_bytes:
            blockers.append({'path': journal.path, 'role': 'journal',
                             'reason': 'recovery_committed_binding_mismatch'})
        for receipt in (transaction, request):
            if receipt is not None:
                image(receipt.path, 'receipt', len(receipt.source_bytes), receipt.sha256, True)
    elif state == 'rolled_back' and 'discard' in data:
        audit = data['discard']
        for name, digest in (('journal.before.json', audit['journal_before_sha256']),
                             ('intent.json', audit['intent_sha256'])):
            path = audit['audit_path'] + '/' + name
            token = observe(path)
            # The journal binds the digest; size is observed, never reconstructed.
            size = token['size'] if token is not None and 'error' not in token else None
            image(path, 'audit', size, digest, True)
    return {'resources': resources, 'blockers': blockers, 'tokens': tokens,
            'critical_inputs_verified': not blockers and state != 'building',
            'complete_target_verified': complete_target,
            'scope': 'prepared_images' if state == 'prepared' else 'state_required_inputs'}
