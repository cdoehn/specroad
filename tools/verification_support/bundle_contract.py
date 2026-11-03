"""Pure Apply bundle and correction contracts; no host operations."""
import base64
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import uuid


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                      separators=(',', ':')).encode()


def validate_bundle(data):
    version = data.get('format_version') if type(data) is dict else None
    fields = {'format_version', 'bundle_number', 'source_result_sha256', 'binding',
              'apply_repository', 'branch', 'initial_dirty', 'stages', 'correction_of'}
    if version == 2:
        fields.add('handoff_kind')
    if (type(data) is not dict or set(data) != fields
            or type(version) is not int or version not in (1, 2)
            or type(data['initial_dirty']) is not bool or data['branch'] != 'dev'
            or not re.fullmatch(r'[0-9]{3,}', data['bundle_number'])
            or not re.fullmatch(r'[0-9a-f]{64}', data['source_result_sha256'])
            or not Path(data['apply_repository']).is_absolute()
            or type(data['stages']) is not list or not data['stages']):
        raise ValueError('Invalid Apply bundle plan')
    if set(data['binding']) != {'repo_id', 'base_commit', 'state_fingerprint', 'fingerprint_algorithm'}:
        raise ValueError('Incomplete native Result binding')
    binding = data['binding']
    identity = uuid.UUID(binding['repo_id'])
    if (identity.version != 4 or str(identity) != binding['repo_id']
            or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', binding['base_commit'])
            or not re.fullmatch(r'[0-9a-f]{16}', binding['state_fingerprint'])
            or binding['fingerprint_algorithm'] != 'patchharbor-state-v1'):
        raise ValueError('Invalid native Result binding')
    ids = []
    for stage in data['stages']:
        stage_fields = {'commit_id', 'message', 'before', 'after', 'payloads', 'source_sha256', 'test_plan'}
        if version == 2:
            stage_fields.add('role')
        if (type(stage) is not dict or set(stage) != stage_fields
                or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', stage['commit_id'])
                or not stage['message'] or '\n' in stage['message'] or '\0' in stage['message']
                or not stage['after'] or set(stage['payloads']) != set(stage['after'])
                or not set(stage['before']) <= set(stage['after'])
                or stage['test_plan']['commit_id'] != stage['commit_id']
                or not re.fullmatch(r'[0-9a-f]{64}', stage['source_sha256'])):
            raise ValueError('Invalid commit stage')
        ids.append(stage['commit_id'])
        for name, digest in {**stage['before'], **stage['after']}.items():
            path = PurePosixPath(name)
            if (path.is_absolute() or str(path) != name or '\\' in name
                    or any(p.lower() in ('.', '..', '.git', '.patchharbor') for p in path.parts)
                    or not re.fullmatch(r'[A-Za-z0-9_./-]+', name)
                    or not re.fullmatch(r'[0-9a-f]{64}', digest)):
                raise ValueError('Unsafe stage path or hash')
        for name, encoded in stage['payloads'].items():
            if sha256(base64.b64decode(encoded, validate=True)).hexdigest() != stage['after'][name]:
                raise ValueError('Stage payload differs from its hash')
        changed_tests = {n for n in stage['after'] if n.startswith('tests/')
                         and PurePosixPath(n).name.startswith('test_') and n.endswith('.py')}
        if not changed_tests <= set(stage['test_plan']['test_files']):
            raise ValueError('Every changed test file must be in the required selection')
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate commit IDs')
    if data['correction_of'] is not None:
        proof = data['correction_of']
        if (set(proof) != {'plan_sha256', 'remaining_commit_ids'}
                or not re.fullmatch(r'[0-9a-f]{64}', proof['plan_sha256'])
                or proof['remaining_commit_ids'] != ids):
            raise ValueError('Correction must retain the exact remaining commit sequence')
    if version == 2:
        roles = [stage['role'] for stage in data['stages']]
        if any(role not in ('clarification', 'implementation', 'correction') for role in roles):
            raise ValueError('Unknown stage role')
        if data['handoff_kind'] == 'patch_ready':
            if 'clarification' in roles:
                raise ValueError('A normal handoff cannot hide clarification')
        elif data['handoff_kind'] == 'patch_ready_with_clarification':
            if roles[0] != 'clarification' or roles.count('clarification') != 1 or 'implementation' not in roles[1:]:
                raise ValueError('Mixed handoff requires one clarification prefix and implementation')
            paths = set(data['stages'][0]['after'])
            required = {'docs/specification/SpecRoad_Spezifikation.md',
                        'docs/implementation/SpecRoad_Implementierungsplan.md'}
            if not required <= paths or any(not (name in required or name == 'verification/catalog.json'
                    or re.fullmatch(r'verification/requirements/SR-TC-[0-9]{4}\.json', name)) for name in paths):
                raise ValueError('Clarification must update specification and plan within the document/catalog scope')
            first = data['stages'][0]
            if any(first['before'].get(name) == first['after'][name] for name in required):
                raise ValueError('Clarification cannot be an unchanged document marker')
            if not any(stage['role'] == 'implementation' and any(
                    not name.startswith(('docs/', 'verification/')) and stage['before'].get(name) != digest
                    for name, digest in stage['after'].items()) for stage in data['stages'][1:]):
                raise ValueError('Mixed handoff requires an actual implementation change')
        else:
            raise ValueError('Unknown handoff classification')
    return data


def public_plan(data):
    return {**{k: v for k, v in data.items() if k not in ('stages', 'apply_repository')},
            'stages': [{k: v for k, v in s.items() if k != 'payloads'} for s in data['stages']]}


def remaining_commits(plan, progress, *, result_head):
    """Use only with an independently native-validated failed Result and its log."""
    ids = [s['commit_id'] for s in plan['stages']]
    done = progress['committed']
    completed_ids = [s['commit_id'] for s in done]
    if (type(progress.get('format_version')) is not int or progress['format_version'] != 1
            or progress.get('kind') != 'specroad-apply-progress-v1'
            or progress['source_result_sha256'] != plan['source_result_sha256']
            or progress['plan_sha256'] != sha256(canonical(plan)).hexdigest()
            or progress['phase'] != 'failed' or completed_ids != ids[:len(done)]
            or len(done) > len(ids) or len(set(ids)) != len(ids)
            or progress['remaining_commit_ids'] != ids[len(done):]
            or progress['actual_head'] != result_head):
        raise ValueError('Unproven remaining commit sequence')
    parent = plan['binding']['base_commit']
    seen = {parent}
    for row in done:
        if (row['parent'] != parent or row['commit'] in seen
                or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', row['commit'])
                or not re.fullmatch(r'[0-9a-f]{64}', row['gate']['selection_sha256'])):
            raise ValueError('Unproven completed commit chain')
        parent = row['commit']
        seen.add(parent)
    if result_head != parent:
        raise ValueError('HEAD moved without a proved completed stage; inspect the Result')
    return plan['stages'][len(done):]


def validate_continuation(previous, progress, data):
    """Bind a correction to the exact failed public plan and retained commit prefix.

    The caller must native-validate the source Result first. This pure helper
    grants neither fresh clarification authority nor permission to replay work.
    """
    validate_bundle(data)
    rest = remaining_commits(previous, progress, result_head=data['binding']['base_commit'])
    expected = {'plan_sha256': sha256(canonical(previous)).hexdigest(),
                'remaining_commit_ids': [s['commit_id'] for s in rest]}
    if (data['format_version'] != previous['format_version'] or data['correction_of'] != expected
            or [s['commit_id'] for s in data['stages']] != expected['remaining_commit_ids']):
        raise ValueError('Correction differs from the bound remaining sequence')
    if data['format_version'] == 2:
        if [s['role'] for s in data['stages']] != [s['role'] for s in rest]:
            raise ValueError('Correction cannot relabel remaining stage roles')
        for old, new in zip(rest, data['stages']):
            if old['role'] == 'clarification' and old['after'] != new['after']:
                raise ValueError('Pending clarification cannot become a new decision')
    return data
