"""Small genuine source variants and the public Merge/Work/Apply handoff."""

from specroad.merge.sources import load_merge_sources
from specroad.model.canonical import canonical_json_bytes as jcs
from support.merge_preparation import baseline_template, adapter_case
from support.merge_relations import history_for
from support.merge_resolution import PLAN_ID, ACTOR, WHEN
from support.domain import domain_value
from support.records import record_value
from support.migration_cli import invoke, success


def templates(root):
    result = []
    for role in ('base', 'ours', 'theirs'):
        goal = domain_value('goal')
        if role == 'ours': goal['title'] = 'Synthetic ours title'
        if role == 'theirs': goal['statement'] = 'Synthetic theirs statement'
        result.append(baseline_template(root/role, values=[record_value('document'), goal]))
    return tuple(result)


def case(root, original, kind='local'):
    requests = [adapter_case(root/role, template, kind)[2]
                for role, template in zip(('base', 'ours', 'theirs'), original)]
    sources = load_merge_sources(*requests)
    history = history_for(sources)
    target = root/'ours'/'local'
    history_path = root/'history.json'; history_path.write_bytes(jcs(history))
    options = {'--history': str(history_path), '--plan-id': PLAN_ID}
    for role, request in zip(('base', 'ours', 'theirs'), requests):
        options['--'+role] = str(request.root); options['--'+role+'-kind'] = kind
        if request.reference is not None: options['--'+role+'-ref'] = request.reference
    authoring = {'--for-apply': True, '--project': str(target), '--actor-type': ACTOR['actor_type'],
        '--actor-id': ACTOR['actor_id'], '--planned-at': WHEN, '--change-plan-id': 'synthetic-public-merge',
        '--request-id': 'synthetic-public-merge-request'}
    return target, sources, history, options, authoring


def work(operation, directory, options=None, representation='argv'):
    return invoke('work.'+operation, options or {}, representation, authorize=False,
                  arguments={'work_dir': str(directory)})


def complete(directory, representation='argv'):
    status = success(work('status', directory, representation=representation))['data']
    total = status['progress']['total_units']
    for _ in range(total+2):
        result = work('resume', directory, representation=representation)
        code = result.exit_code
        assert code in (0, 1, 8), (result.diagnostics, result.details)
        if code != 8:
            return result
    raise AssertionError('Merge Work did not complete its finite inventory')


def publication(root, data, mode='direct', representation='argv'):
    target, sources, history, options, authoring = data
    prepare_options = {**options, **authoring}
    directory = None
    if mode != 'direct':
        directory = root/'work'
        first = invoke('merge.plan', {**options, '--work-dir': str(directory)}, representation, authorize=False)
        assert first.exit_code == 8, (first.diagnostics, first.details)
        if mode == 'portable':
            transport = root/'transport'; transport.mkdir()
            package = transport/'work.zip'
            success(work('export', directory, {'--output': str(package)}, representation))
            restored = root/'restored'
            success(invoke('work.restore', {'--output': str(restored)}, representation,
                           arguments={'file': str(package)}, authorize=False))
            directory = restored
        completed = complete(directory, representation)
        assert completed.exit_code == 0, completed
        prepare_options['--work-dir'] = str(directory)
    document = success(invoke('merge.plan', prepare_options, representation, authorize=False))
    assert document['format_version'] == 'merge-publication-plan-v1', document
    plan_path = root/'publication.json'; plan_path.write_bytes(jcs(document['change_plan']))
    backup = root/'backup'; backup.mkdir()
    apply_options = {key: value for key, value in options.items() if key.startswith(('--base', '--ours', '--theirs'))}
    apply_options.update({'--project': str(target), '--expected-plan-sha256': document['change_plan_sha256'],
        '--backup-root': str(backup), '--backup': 'before.zip', '--transaction-id': 'synthetic-public-merge-txn'})
    return document, plan_path, apply_options, directory


def example_inputs(root, command):
    from support.merge_publication import setup
    target, plan, args, _ = setup(root)
    filename = root/'publication.json'; filename.write_bytes(plan.source_bytes)
    options = {'--project': str(target), '--expected-plan-sha256': plan.sha256,
        '--backup-root': args['backup_descriptor']['output_root'], '--backup': 'before.zip',
        '--transaction-id': args['transaction_id'], '--format': 'json'}
    options.update({'--'+role: getattr(args['sources'], role).source_root for role in ('base', 'ours', 'theirs')})
    return {'command_id': command.command_id, 'arguments': {'merge_plan': str(filename)}, 'options': options}
