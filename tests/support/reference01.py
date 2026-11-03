"""Synthetic source fixtures. Their actors never claim real human decisions.

No reader/canonicalizer under test generates the input bytes or expected hashes.
"""
import copy
import json
import re
from hashlib import sha256
from pathlib import Path
from .domain import domain_value, PREFIXES as DOMAIN
from .records import record_value, PREFIXES as RECORDS

CONTRACT = Path(__file__).resolve().parents[2] / 'docs/specification/reference-0.1-v1.0.1'
SCOPE = {'scope_version': 'reference01-scope-v1', 'scope_kind': 'project',
         'selector': {}, 'configuration_id': None, 'boundary_policy': 'closed'}
ACTOR = {'actor_type': 'human', 'actor_id': 'synthetic-author'}
TIME = '2026-11-03T00:00:00Z'


def encoded(value):
    # Authored fixture keys are ASCII, numbers small; independent JCS oracle.
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def digest(value):
    return sha256(encoded(value)).hexdigest()


def minimal():
    root = CONTRACT / 'vectors/project'
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def path(value):
    types = json.loads((CONTRACT / 'artifact-types.json').read_bytes())
    return 'spec/' + types[value['artifact_type']]['directory'] + '/' + value['id'] + '.json'


def put(files, value):
    files[path(value)] = encoded(value) + b'\n'
    return value


def scope(kind='project', selector=None):
    return {'scope_version': 'scope-v1', 'scope_kind': kind, 'selector': selector or {},
            'configuration_id': None, 'closure_profile': 'core-closure-v1', 'boundary_policy': 'closed'}


def artifact(kind):
    value = domain_value(kind) if kind in DOMAIN else record_value(kind)
    # Only synthetic fixture construction; production source values are never
    # rewritten or passed to the current artifact loader.
    raw = json.dumps(value)
    raw = re.sub(r'SR-([A-Z]+)-0{26}', r'SR-\1-0001', raw)
    raw = re.sub(r'SR-([A-Z]+)-1{26}', r'SR-\1-0002', raw)
    value = json.loads(raw); value['schema_version'] = '0.1.0'; value.pop('id_scheme')
    for relation in value['relations']:
        relation.pop('relation_id', None); relation.pop('id_scheme', None)
    if kind == 'requirement':
        value.pop('language'); value.pop('normative_force')
    value.update(created_at=TIME, updated_at=TIME, created_by=ACTOR, updated_by=ACTOR)
    return value


def relation(kind, target, **extra):
    return {'type': kind, 'target': target, 'external_identities': [], 'extensions': {}, **extra}


def context(value):
    excluded = {'revision', 'created_at', 'created_by', 'updated_at', 'updated_by', 'maturity',
        'implementation_status', 'verification_plan_status', 'verification_waiver', 'relations',
        'tags', 'proposal_status', 'evidence_state', 'baseline_state', 'review_state'}
    return digest({k: v for k, v in value.items() if k not in excluded})


def snapshot(files):
    entries, payload = [], {}
    for name, raw in sorted(files.items()):
        if name == 'specroad.json': role = 'configuration'
        elif name == 'profiles/core-reference01.json': role = 'profile'
        elif name.startswith('spec/'): role = 'artifact'
        elif name.startswith('archive/'): continue
        else: role = 'attachment'
        value = {} if role == 'attachment' else json.loads(raw)
        entries.append({'path': name, 'role': role, 'artifact_id': value.get('id'),
            'revision': value.get('revision'), 'media_type': 'application/octet-stream' if role == 'attachment' else 'application/json',
            'size': len(raw), 'byte_sha256': sha256(raw).hexdigest(),
            'canonical_sha256': None if role == 'attachment' else digest(value)})
        address = 'archive/objects/' + sha256(raw).hexdigest()[:2] + '/' + sha256(raw).hexdigest()
        payload[address] = raw
    model = {'algorithm': 'reference01-model-root-v1', 'project_id': 'synthetic-reference-project',
        'scope_descriptor': SCOPE, 'entries': [{k: v for k, v in e.items()
            if e['role'] == 'attachment' or k not in ('size', 'byte_sha256')} for e in entries]}
    return entries, digest(model), payload


def seal(files, number=1, **updates):
    entries, root, objects = snapshot(files)
    baseline = artifact('baseline')
    baseline.update(id=f'SR-BASE-{number:04}', scope_descriptor=SCOPE, manifest=entries,
        model_root_sha256=root, model_root_algorithm='reference01-model-root-v1',
        project_id='synthetic-reference-project', profiles=['core-reference01@1.0.0'], **updates)
    files.update(objects); put(files, baseline)
    return baseline


def basis_root(files):
    # Independent source-basis oracle over authored fixture data.
    ordinary = {p: raw for p, raw in files.items() if not p.startswith('spec/')
        or json.loads(raw)['artifact_type'] not in ('baseline', 'proposal')}
    rows, _, _ = snapshot(ordinary)
    return digest({'algorithm': 'reference01-proposal-basis-v1',
        'project_id': 'synthetic-reference-project', 'scope_descriptor': scope('specification'),
        'entries': [{k: v for k, v in r.items() if r['role'] == 'attachment'
                    or k not in ('size','byte_sha256')} for r in rows]})


def full_project():
    files = minimal(); base = seal(files)
    values = {kind: artifact(kind) for kind in (*DOMAIN, *RECORDS)
              if kind not in ('goal', 'document', 'baseline')}
    goal = json.loads(files['spec/goals/SR-GOAL-0001.json'])
    document = json.loads(files['spec/documents/SR-DOC-0001.json'])
    document['revision'] += 1
    document['relations'] = [relation('contains', 'SR-SEC-0001', position=0)]; put(files, document)
    values['section']['relations'] = [relation('contains', 'SR-BLOCK-0001', position=0)]
    values['requirement']['relations'] = [relation('addresses', goal['id']), relation('verified_by', 'SR-VER-0001')]
    values['verification'].update(configuration_policy='independent')
    values['view']['scope_descriptor'] = scope()
    values['code_ref']['path'] = 'src/reference.py'
    code = b'raise RuntimeError("source must never execute")\r\n'
    files['src/reference.py'] = code; values['code_ref']['file_sha256'] = sha256(code).hexdigest()
    source = values['requirement']
    values['evidence'].update(context_hash_algorithm='reference01-verification-context-v1',
        subjects=[{'artifact_id': source['id'], 'revision': source['revision'],
                   'artifact_sha256': digest(source), 'verification_context_sha256': context(source)}])
    review = values['relation_review']; review.pop('relation_id')
    review.update(context_hash_algorithm='reference01-relation-context-v1',
        relation_locator={'source_id': source['id'], 'index': 0}, source_id=source['id'], target_id=goal['id'],
        source_revision=source['revision'], target_revision=goal['revision'], source_artifact_sha256=digest(source),
        target_artifact_sha256=digest(goal), source_context_sha256=context(source), target_context_sha256=context(goal),
        relation_content_sha256=digest(source['relations'][0]), reviewed_at=TIME)
    extra = copy.deepcopy(values['component']); extra['id'] = 'SR-COMP-0002'; put(files, extra)
    for kind, value in values.items():
        if kind != 'proposal':put(files, value)
    proposal = values['proposal']
    original_basis = basis_root(files)
    proposal['base'] = {'scope_descriptor': scope('specification'), 'model_root_sha256': original_basis}
    plan = {'format_version': '1.2.0', 'metadata_policy_version': 'change-metadata-v1',
        'change_plan_id': 'CP-' + '0' * 26, 'request_id': 'synthetic:source', 'planned_at': TIME,
        'actor': ACTOR, 'base': copy.deepcopy(proposal['base']), 'operations': [], 'preconditions': [],
        'result_artifacts': [], 'expected_result': {'model_root_sha256': original_basis}}
    plan['change_plan_sha256'] = digest(plan); proposal['change_plan'] = plan
    excluded = {'revision', 'created_at', 'created_by', 'updated_at', 'updated_by', 'content_revision',
        'content_sha256', 'maturity', 'proposal_status', 'reviews', 'control_history'}
    proposal['content_sha256'] = digest({k: v for k, v in proposal.items() if k not in excluded})
    put(files, proposal)
    return files


def release_project():
    """Original selection/integrity fixture, never a current human release approval."""
    files = full_project(); seal(files, 9)
    evidence = json.loads(files['spec/evidence/SR-EVD-0001.json'])
    code = files['src/reference.py']
    subject = {'subject_id': 'fixture-product', 'manifest': [{'logical_path': 'src/reference.py',
        'size': len(code), 'sha256': sha256(code).hexdigest()}]}
    subject['state_sha256'] = digest(subject)
    evaluation = {'format_version': '1.0.0', 'evaluation_id': 'EVAL-' + '0' * 26,
        'evaluated_subject': subject, 'configuration_hash': None,
        'required_runs': [{'subject_artifact_id': 'SR-REQ-0001', 'contract_id': 'SR-VER-0001',
            'test_id': None, 'check_id': 'overall', 'run_ids': ['test-ci:run-1']}],
        'replacements': [], 'created_at': TIME, 'created_by': ACTOR}
    evidence['id'] = 'SR-EVD-0002'; evidence['result'] = 'passed'; evidence['run_context']['subject_state_sha256'] = subject['state_sha256']; put(files, evidence)
    first = json.loads(files['spec/releases/SR-REL-0001.json'])
    first['revision'] += 1
    first['readiness_policy'] = {'format_version': '1.0.0', 'blocker_decisions': [], 'verification_evaluation': evaluation}
    put(files, first)
    second = copy.deepcopy(first); second['id'] = 'SR-REL-0002'; second['revision'] = 1; put(files, second)
    seal(files, 2, baseline_kind='release', release_id=second['id'], verification_evaluation=evaluation)
    return files
