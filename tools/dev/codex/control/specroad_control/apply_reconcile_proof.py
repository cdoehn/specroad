"""Passive, bounded evidence for an explicitly requested byte-preserving Apply restart."""
import ast
import base64
from copy import deepcopy
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import re
import stat
import zipfile
import zlib

from .contracts import binding, timestamp
from .config import digest
from .errors import ControlError
from .local import decode_object

LIMIT = 32 * 1024 * 1024
PLAN_LIMIT = 64 * 1024 * 1024
MARKER = "SPECROAD_APPLY_COMMIT_PLAN"


def fail(message):
    raise ControlError('apply_reconciliation_unproven', message)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                      separators=(',', ':')).encode()


def hashed(value):
    return sha256(canonical(value)).hexdigest()


def archive_bytes(fact):
    """Open one bounded regular inode without following a replaced symlink/FIFO."""
    fd = os.open(fact['path'], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 512 * 1024 * 1024:
            fail('Archive is not a bounded regular file.')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(512 * 1024 * 1024 + 1)
        if len(raw) > 512 * 1024 * 1024 or sha256(raw).hexdigest() != fact['sha256']:
            fail('Native-validated archive bytes changed.')
        return raw
    finally:
        os.close(fd)


def member(fact, name, *, inventory=False):
    """Recheck exact native-validated archive bytes; never extract or execute them."""
    raw = archive_bytes(fact)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if inventory:
            return [entry.filename for entry in archive.infolist()]
        matches = [entry for entry in archive.infolist() if entry.filename == name]
        if len(matches) != 1 or matches[0].file_size > LIMIT:
            fail('Missing, duplicate or oversized proof member.')
        return archive.read(matches[0])


def public_plan(data):
    return {**{k: v for k, v in data.items() if k not in ('stages', 'apply_repository')},
            'stages': [{k: v for k, v in stage.items() if k != 'payloads'} for stage in data['stages']]}


def plan(fact, *, data_limit=PLAN_LIMIT):
    if type(data_limit) is not int or not 0 < data_limit <= PLAN_LIMIT:
        fail('Commit plan limit must be a positive integer no greater than 64 MiB.')
    metadata = decode_object(member(fact, 'patch.json'))
    expected_members = {'patch.json', 'run.sh', 'PATCHHARBOR_META/environment.json',
                        'PATCHHARBOR_META/CHAT_INSTRUCTIONS.md'}
    names = member(fact, None, inventory=True)
    if metadata['entrypoint'] != 'run.sh' or len(names) != len(expected_members) or set(names) != expected_members:
        fail('Only the reviewed native single-entrypoint package is supported.')
    script = member(fact, metadata['entrypoint']).decode('utf-8')
    prefix, body = script.split("<<'" + MARKER + "'\n")
    body, suffix = body.split('\n' + MARKER + '\n')
    nodes = [node for node in ast.parse(body).body if isinstance(node, ast.Assign)
             and any(isinstance(target, ast.Name) and target.id == 'DATA' for target in node.targets)]
    if len(nodes) != 1 or len(nodes[0].targets) != 1:
        fail('One literal compressed DATA assignment is required.')
    node = nodes[0]
    source_lines = body.splitlines(keepends=True)
    if (node.col_offset != 0 or node.lineno != node.end_lineno
            or node.end_col_offset != len(source_lines[node.lineno - 1].rstrip('\r\n'))):
        fail('The DATA assignment must occupy exactly one complete statement line.')
    # Only this reviewed literal grammar is data. No eval, imports or code execution.
    value = node.value
    for module, function in [('json', 'loads'), ('zlib', 'decompress'), ('base64', 'b64decode')]:
        if (not isinstance(value, ast.Call) or value.keywords or len(value.args) != 1
                or not isinstance(value.func, ast.Attribute) or value.func.attr != function
                or not isinstance(value.func.value, ast.Name) or value.func.value.id != module):
            fail('Unsupported Apply plan encoding.')
        value = value.args[0]
    if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
        fail('Plan encoding is not literal.')
    compressed = base64.b64decode(value.value, validate=True)
    decoder = zlib.decompressobj()
    raw = decoder.decompress(compressed, data_limit + 1)
    if len(raw) > data_limit or not decoder.eof or decoder.unused_data:
        fail('Incomplete or oversized compressed plan.')
    data = decode_object(raw)
    fields = {'format_version', 'bundle_number', 'source_result_sha256', 'binding',
              'apply_repository', 'branch', 'initial_dirty', 'stages', 'correction_of'}
    version = data.get('format_version')
    if version == 2:
        fields.add('handoff_kind')
    if (set(data) != fields or type(version) is not int or version not in (1, 2)
            or data['branch'] != 'dev' or type(data['initial_dirty']) is not bool
            or not re.fullmatch('[0-9]{3,}', data['bundle_number'])
            or not Path(data['apply_repository']).is_absolute()
            or not isinstance(data['stages'], list) or not data['stages']):
        fail('Unsupported Apply plan contract.')
    binding(data['binding'])
    digest(data['source_result_sha256'])
    ids = []
    for stage in data['stages']:
        stage_fields = {'commit_id', 'message', 'before', 'after', 'payloads', 'source_sha256', 'test_plan'} | ({'role'} if version == 2 else set())
        if (not isinstance(stage, dict) or set(stage) != stage_fields
                or not re.fullmatch('[A-Za-z0-9_.-]{1,128}', stage['commit_id'])
                or not isinstance(stage['message'], str) or not stage['message']
                or '\n' in stage['message'] or '\0' in stage['message']
                or not all(isinstance(stage[key], dict) for key in ('before', 'after', 'payloads', 'test_plan'))
                or not stage['after'] or set(stage['payloads']) != set(stage['after'])
                or not set(stage['before']) <= set(stage['after'])
                or stage['test_plan']['commit_id'] != stage['commit_id']):
            fail('Invalid commit stage.')
        ids.append(stage['commit_id'])
        digest(stage['source_sha256'])
        for name, value in {**stage['before'], **stage['after']}.items():
            digest(value)
            if (not re.fullmatch('[A-Za-z0-9_./-]+', name) or str(Path(name)) != name
                    or Path(name).is_absolute() or any(part.lower() in ('.', '..', '.git', '.patchharbor')
                                                     for part in Path(name).parts)):
                fail('Unsafe stage path.')
        for name, encoded in stage['payloads'].items():
            if sha256(base64.b64decode(encoded, validate=True)).hexdigest() != stage['after'][name]:
                fail('Payload differs from its promised bytes.')
    if len(ids) != len(set(ids)):
        fail('Duplicate commit IDs.')
    if version == 2:
        correction = data['correction_of']
        if correction is not None:
            if (type(correction) is not dict or set(correction) != {'plan_sha256', 'remaining_commit_ids'}
                    or correction['remaining_commit_ids'] != ids):
                fail('Correction must bind the complete remaining sequence.')
            digest(correction['plan_sha256'])
        from .mixed_contract import validate_roles
        validate_roles(data)
    lines = source_lines
    lines[node.lineno - 1:node.end_lineno] = ['DATA = {}\n']
    # Entire shell wrapper and Python program must be byte-identical too.
    program = prefix + ''.join(lines) + suffix
    return data, sha256(program.encode()).hexdigest()


def compare(original, resumed, source, checkpoint):
    left, left_program = plan(original)
    right, right_program = plan(resumed)
    if left['format_version'] == 2 and left['stages'][0]['role'] == 'clarification':
        fail('An unfinished clarification requires a native failed Apply Result and its original plan; a recovery checkpoint is not continuation authority.')
    if (left_program != right_program or left['binding'] != source['binding']
            or left['source_result_sha256'] != source['sha256']
            or right['binding'] != checkpoint['binding']
            or right['source_result_sha256'] != checkpoint['sha256']
            or left['apply_repository'] != source['repository_path']
            or left['apply_repository'] != checkpoint['repository_path']):
        fail('Source or entrypoint program differs.')
    expected = deepcopy(left)
    expected.update(binding=checkpoint['binding'], source_result_sha256=checkpoint['sha256'],
                    bundle_number=right['bundle_number'],
                    correction_of={'plan_sha256': hashed(public_plan(left)),
                                   'remaining_commit_ids': [s['commit_id'] for s in left['stages']]})
    expected['stages'][0]['before'] = expected['stages'][0]['after']
    if right != expected or not right['initial_dirty'] or right['bundle_number'] == left['bundle_number']:
        fail('The continuation changed or omitted original work.')
    return right, {'original_plan_sha256': hashed(public_plan(left)),
                   'resumed_plan_sha256': hashed(public_plan(right)), 'program_sha256': left_program}


def completion(result, data):
    lines = member(result, 'logs/execution.log').decode('utf-8').splitlines()
    plans = [decode_object(line[len('SPECROAD_APPLY_PLAN '):]) for line in lines
             if line.startswith('SPECROAD_APPLY_PLAN ')]
    progress = [decode_object(line[len('SPECROAD_APPLY_PROGRESS '):]) for line in lines
                if line.startswith('SPECROAD_APPLY_PROGRESS ')]
    if plans != [public_plan(data)] or not progress:
        fail('Apply log does not prove the exact continuation plan.')
    final = progress[-1]
    if (final.get('kind') != 'specroad-apply-progress-v1' or final.get('format_version') != 1
            or final.get('phase') != 'completed' or final.get('error') is not None
            or final.get('active_commit_id') is not None or final.get('remaining_commit_ids') != []
            or final.get('plan_sha256') != hashed(plans[0])
            or final.get('source_result_sha256') != data['source_result_sha256']
            or final.get('actual_head') != result['completed_commit']
            or len(final['committed']) != len(data['stages'])):
        fail('Incomplete Apply completion evidence.')
    parent = data['binding']['base_commit']
    seen = {parent}
    for stage, row in zip(data['stages'], final['committed']):
        gate = row['gate']
        if (row['commit_id'] != stage['commit_id'] or row['parent'] != parent
                or row['commit'] in seen or not re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}', row['commit'])
                or not re.fullmatch('[0-9a-f]{64}', gate['selection_sha256'])
                or not re.fullmatch('[0-9a-f]{64}', gate['observations_sha256'])
                or type(gate['tests']) is not int or type(gate['required_tests']) is not int
                or not 0 < gate['required_tests'] <= gate['tests']
                or type(gate['partition_index']) is not int or gate['partition_index'] < 0):
            fail('Commit parent chain or test gates are unproven.')
        parent = row['commit']
        seen.add(parent)
    if parent != result['completed_commit']:
        fail('Completed commit does not match the proven chain.')
    return hashed(final)


def unique(items, message):
    selected = {item['sha256']: item for item in items}
    if len(selected) != 1:
        fail(message)
    return next(iter(selected.values()))


def artifacts(engine, source, original_sha, requested, *, check_current=True):
    """Resolve all five artifacts through native validation, never by newest filename."""
    source = engine.exchange.source(source)
    result = engine.exchange.source(requested)
    if (not result['success'] or result['primary_kind'] != 'success' or result['dirty']
            or result['dry_run'] or result['operation'] != 'apply' or not result['entrypoint_started']
            or not result['completed_commit'] or result['completed_commit'] != result['binding']['base_commit']
            or result['repository_path'] != source['repository_path']):
        fail('Requested Result is not a clean committed Apply success.')
    original = unique((p for p in engine.exchange.patches(source) if p['sha256'] == original_sha),
                      'The original native-bound patch is missing.')
    if engine.exchange.following(source, original_sha):
        fail('An original terminal Result exists; normal processing takes priority.')
    resumed = unique((p for p in engine.exchange.candidates('patch', lambda m: all(
        m.get(k) == v for k, v in result['expected'].items())) if p['sha256'] == result['patch_sha256']),
        'The applied continuation patch is missing.')
    data, _ = plan(resumed)
    checkpoint = unique((p for p in engine.exchange.candidates('result', lambda m: all(
        m.get(k) == v for k, v in result['expected'].items())) if p['sha256'] == data['source_result_sha256']),
        'The exact intermediate Result is missing.')
    if (checkpoint['dry_run'] or checkpoint['operation'] != 'bundle' or not checkpoint['dirty']
            or not checkpoint['success'] or checkpoint['binding'] != result['expected']
            or any(checkpoint['binding'][k] != source['binding'][k] for k in
                   ('repo_id', 'base_commit', 'fingerprint_algorithm'))
            or checkpoint['binding']['state_fingerprint'] == source['binding']['state_fingerprint']):
        fail('The intermediate snapshot is not the same uncommitted base.')
    resumed = engine.core.validate(Path(resumed['path']), checkpoint)
    following = engine.exchange.following(checkpoint, resumed['sha256'])
    if unique(following, 'Ambiguous continuation results.')['sha256'] != result['sha256']:
        fail('Requested Result is not the unique continuation result.')
    data, hashes = compare(original, resumed, source, checkpoint)
    hashes['completion_sha256'] = completion(result, data)
    if data['format_version'] == 2:
        # Legacy proof records stay byte-stable; typed recovery additionally
        # proves that the clean Result contains every promised final file.
        from .apply_snapshot import snapshot, apply_stage
        _, files = snapshot(checkpoint)
        for stage in data['stages']:
            files = apply_stage(files, stage)
        if snapshot(result) != (files, files):
            fail('Typed recovery Result differs from the completed payloads.')
    sequence = [source, checkpoint, result]
    stamps = [timestamp(item.get('captured_at')) for item in sequence]
    if any(stamp is None for stamp in stamps) or not stamps[0] < stamps[1] <= stamps[2]:
        fail('Artifact chronology is missing or contradictory.')
    if check_current:
        engine.exchange.assert_current(result, {item['run_id'] for item in sequence})
    return {'source': source, 'original': original, 'checkpoint': checkpoint,
            'resumed': resumed, 'result': result, **hashes}


def prove(engine, source, original_sha, requested, *, check_current=True):
    try:
        return artifacts(engine, source, original_sha, requested, check_current=check_current)
    except ControlError:
        raise
    except (OSError, ValueError, TypeError, KeyError, IndexError, SyntaxError, RecursionError,
            zipfile.BadZipFile, zlib.error, RuntimeError, NotImplementedError, OverflowError):
        fail('Malformed or unavailable Apply continuation evidence.')
