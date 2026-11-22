"""Fresh interpreters for owned fault cases, preserving their native inputs.

Only trusted tests construct these requests. No live callable, descriptor,
thread, database connection or acquired lock crosses into the fault process.
"""
import json
from pathlib import Path

from support.processes import run_python

ROOT = Path(__file__).resolve().parents[2]


class NativeCall:
    def __init__(self, directory, action, request):
        self.directory = directory
        self.action = action
        self.request = request

    def __call__(self):
        return self.action()


def native_call(directory, kind, root, plan, args, action, *, before=None):
    options = {k: v for k, v in args.items() if k not in ('authority', 'sources', 'services')}
    request = {'kind': kind, 'root': str(root), 'plan': plan.source_bytes.decode(), 'options': options}
    if kind == 'merge':
        assert args['services'] is None
        request['sources'] = [getattr(args['sources'], role).source_root
                              for role in ('base', 'ours', 'theirs')]
    if kind == 'change':
        request['before'] = {path: raw.hex() for path, raw in before.items()}
    return NativeCall(directory, action, request)


def restart_call(root, request, transaction, statement):
    from support.git_restart import new_write
    return NativeCall(root.parent, lambda: new_write(root, request, transaction, statement),
        {'kind': 'restart', 'root': str(root), 'request': request,
         'transaction': transaction, 'statement': statement})


def invoke(value):
    from specroad.changes import ChangePlan, PublicationAuthority
    root = Path(value['root'])
    kind = value['kind']
    if kind == 'restart':
        from support.git_restart import new_write
        return new_write(root, value['request'], value['transaction'], value['statement'])
    plan = ChangePlan(value['plan'].encode())
    args = dict(value['options'])
    if kind == 'change':
        from specroad.changes import prepare_publication_check
        from specroad.model.model_manifest import ProjectReadBinding
        from support.targets import model, POLICY
        from test_write_guard import publish
        before = {path: bytes.fromhex(raw) for path, raw in value['before'].items()}
        assert all((root / path).read_bytes() == raw for path, raw in before.items())
        config = json.loads(before['specroad.json'])
        info = root.stat()
        current = model([json.loads(raw) for path, raw in before.items() if path.startswith('spec/')],
            config=config, profiles=[json.loads(raw) for path, raw in before.items() if path.startswith('profiles/')],
            binding=ProjectReadBinding(config['project_id'], str(root), (info.st_dev, info.st_ino)))
        assert current.source_files == before
        check = prepare_publication_check(plan, current, policy=POLICY)
        return publish(root, check).data
    if kind == 'migration':
        from specroad.migration.transaction import apply_migration_plan
        args['authority'] = PublicationAuthority('synthetic-host', '1', lambda request: True)
        return apply_migration_plan(root, plan.source_bytes, **args)
    assert kind == 'merge'
    from specroad.merge import SourceRequest, load_merge_sources, apply_merge_publication
    args['sources'] = load_merge_sources(*(SourceRequest(Path(path)) for path in value['sources']))
    args['authority'] = PublicationAuthority('synthetic-merge-host', '1', lambda request: True)
    args['services'] = None
    return apply_merge_publication(root, plan.source_bytes, **args)


def fault_process(call, point, fault):
    request = call.directory / 'fault-process-input.json'
    request.write_text(json.dumps(call.request), encoding='utf-8')
    paths = [str(ROOT / name) for name in ('src', 'tests', 'tools')]
    body = ('import json,sys\nfrom pathlib import Path\nsys.path[:0] = ' + repr(paths) + '\n'
        + 'from support.write_fault_process import invoke\n'
        + 'from support.write_faults import execute\n'
        + 'value=json.loads(Path(sys.argv[1]).read_bytes())\n'
        + 'execute(lambda: invoke(value),sys.argv[2],sys.argv[3])\n')
    # The existing native checkpoint/exit code is the oracle. A slow valid
    # write is not killed by an arbitrary per-fixture wall-clock deadline.
    return run_python(['-I', '-B', '-c', body, str(request), point, fault],
                      call.directory, capture=True)
