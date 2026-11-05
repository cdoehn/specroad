"""Passive source/terminal evidence for explicit blocked-attempt authorization."""
from hashlib import sha256
from .apply_reconcile_proof import member
from .blocked_authorization_history import active
from .errors import ControlError
from .job_contract import contract, scope
from .local import decode_object, read_private
from .mixed_contract import supports_v4
from .retry_ledger import attempt_directory


PATH = 'verification/blocked_clarification_authorization.json'

CAPABILITY = {'format_version': 1, 'decision_rule': 'SPECROAD-DECISION-1',
              'decision_contract_version': 4, 'authorization_mode': 'explicit_blocked_attempt',
              'budget_policy': 'preserve', 'maximum_grants_per_source': 1}

def fail(message):
    raise ControlError('blocked_clarification_rejected', message)

def evidence(engine, doc):
    source = doc['source']
    directory = attempt_directory(engine.paths, source['sha256'], doc['attempt_number'])
    files = {}
    values = {}
    for name in ('attempt.json', 'dispatch.json', 'protocol-completion.json', 'completion.json'):
        try:
            raw = read_private(directory / name)
        except FileNotFoundError:
            if name != 'dispatch.json':
                fail('The original blocked attempt and both completion records are required.')
            values[name] = None
            continue
        values[name], files[name] = sha256(raw).hexdigest(), decode_object(raw)
    attempt, terminal, answer = files['attempt.json'], files['protocol-completion.json'], files['completion.json']
    if (attempt.get('source_sha256') != source['sha256']
            or attempt.get('thread_id') != engine.config.session_id
            or attempt.get('number') != doc['attempt_number']
            or contract(attempt.get('request_contract')) != doc['previous_contract']
            or attempt.get('request_source') != {k: source[k] for k in ('path', 'sha256', 'binding', 'run_id')}
            or terminal.get('completed') is not True or terminal.get('thread_id') != engine.config.session_id
            or terminal.get('transport') != engine.config.transport or terminal.get('answer') != answer
            or set(answer) != {'source_result_sha256', 'status', 'patch_sha256', 'message'}
            or not all(isinstance(v, str) for v in answer.values())
            or answer['source_result_sha256'] != source['sha256']
            or answer['status'] != 'blocked' or answer['patch_sha256'] != ''):
        fail('No exact terminal patchless blocked answer with its original authority.')
    if type(attempt.get('number')) is not int:
        fail('Attempt number must be an exact integer.')
    if engine.config.transport == 'app-server-proxy':
        dispatch = files.get('dispatch.json', {})
        if (not isinstance(terminal.get('turn_id'), str) or not terminal['turn_id']
                or dispatch.get('turn_id') != terminal['turn_id']
                or dispatch.get('thread_id') != engine.config.session_id):
            fail('The exact proxy turn dispatch and completion are required.')
        from .continuation import request_prompt
        prompt = request_prompt(attempt, source)
        if dispatch.get('prompt_sha256') != sha256(prompt.encode()).hexdigest():
            fail('The proxy dispatch does not bind the original request prompt.')
    return values

def verify(engine, ledger, doc, *, require_unused=True):
    if (scope(engine.config) != doc['scope']
            or sha256(read_private(engine.paths.config)).hexdigest() != doc['config_sha256']
            or evidence(engine, doc) != doc['evidence']):
        fail('Configuration or original completion evidence changed.')
    source = engine.exchange.source(doc['source'])
    raw = member(source, 'base/' + PATH)
    capability = decode_object(raw)
    if (len(raw) > 4096 or set(capability) != set(CAPABILITY)
            or any(type(capability[k]) is not type(v) or capability[k] != v for k, v in CAPABILITY.items())
            or not supports_v4(source) or not source['success'] or source['dirty'] or source['dry_run']):
        fail('The clean native Result must explicitly support blocked-attempt authorization.')
    if require_unused:
        engine.exchange.assert_current(source, ledger.known_runs())
        # Check all native-bound outputs, not only the engine's filtered list.
        if engine.exchange.patches(source):
            fail('A bound patch already exists; adoption takes priority over a new attempt.')
    if evidence(engine, doc) != doc['evidence'] or sha256(read_private(engine.paths.config)).hexdigest() != doc['config_sha256']:
        fail('Evidence changed during native validation.')

def guard_original(engine, ledger, source):
    doc = active(ledger, source['sha256'])
    if doc is not None and (scope(engine.config) != doc['scope']
            or sha256(read_private(engine.paths.config)).hexdigest() != doc['config_sha256']
            or evidence(engine, doc) != doc['evidence']):
        fail('Original authorization inputs changed at dispatch.')
