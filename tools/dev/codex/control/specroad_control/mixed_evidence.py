"""Passive v4 plan, prefix and real snapshot proof. No patch code is executed."""
import zipfile
import zlib
from .apply_reconcile_proof import plan, public_plan, hashed, unique, completion
from .apply_snapshot import snapshot, apply_stage
from .mixed_contract import MIXED, supports_v4, remaining_roles
from .errors import ControlError
from .blocked_chain_proof import test_selection
from .mixed_progress import fail, progress, source_parent


def handoff(engine, source, patch, selected, status):
    if not supports_v4(source):
        fail('The native source does not contain the installed project opt-in.')
    data, _ = plan(patch)
    if (data['format_version'] != 2 or data['handoff_kind'] != status
            or data['source_result_sha256'] != source['sha256'] or data['binding'] != source['binding']
            or data['apply_repository'] != source['repository_path'] or data['initial_dirty'] != source['dirty']):
        fail('The classified ZIP differs from the request or actual source.')
    if source['success']:
        if data['correction_of'] is not None or selected['clarification_continuation']:
            fail('A successful source does not authorize an invented remaining clarification.')
    else:
        previous, failed = source_parent(engine, source)
        expected = {'plan_sha256': hashed(previous), 'remaining_commit_ids': failed['remaining_commit_ids']}
        if data['correction_of'] != expected:
            fail('A failed source requires the exact complete remaining sequence.')
        rest = remaining_roles(previous, failed, data)
        from .handoff_rebase import candidate, require_remaining_scope
        if candidate(source):
            require_remaining_scope(rest, data['stages'])
        pending = bool(rest and rest[0]['role'] == 'clarification')
        if selected['clarification_continuation'] != pending or (pending and status != MIXED):
            fail('Continuation authority does not match the actual unfinished prefix.')
    if status == MIXED and not (selected['clarification_allowed'] or selected['clarification_continuation']):
        fail('No clarification authority.')
    base, files = snapshot(source)
    dirty = {p for p in set(base) | set(files) if base.get(p) != files.get(p)}
    if not dirty <= set(data['stages'][0]['payloads']):
        fail('The first stage omits retained uncommitted work.')
    for stage in data['stages']:
        test_selection(stage)
        # New/modified behavior tests remain mandatory before each actual commit.
        changed_tests = {n for n in stage['after'] if n.startswith('tests/') and n.rsplit('/', 1)[-1].startswith('test_') and n.endswith('.py')}
        if not changed_tests <= set(stage['test_plan'].get('test_files', [])):
            fail('Changed behavior tests are absent from the mandatory gate.')
        files = apply_stage(files, stage)
    return data


def followup(engine, source, patch_sha, result, output_kind):
    patch = unique((p for p in engine.exchange.patches(source) if p['sha256'] == patch_sha), 'Pending typed ZIP is missing.')
    from .handoff_rebase import candidate, rejection
    if candidate(result):
        data = rejection(engine, source, patch, result)
        if (data['handoff_kind'] != output_kind or result['binding'] == source['binding']):
            fail('The rejected handoff cannot authorize this successor.')
        return {'verified': True, 'pending_clarification': data['stages'][0]['role'] == 'clarification'}
    data, _ = plan(patch)
    if (data['format_version'] != 2 or data['source_result_sha256'] != source['sha256']
            or data['binding'] != source['binding'] or result['expected'] != source['binding']
            or result['patch_sha256'] != patch_sha or result['dry_run'] or result['operation'] != 'apply'
            or not result['entrypoint_started'] or data['initial_dirty'] != source['dirty']
            or data['binding'] != patch['binding']
            or data['apply_repository'] != source['repository_path']
            or result['repository_path'] != source['repository_path']
            or output_kind in ('patch_ready', MIXED) and data['handoff_kind'] != output_kind):
        fail('Follow-up does not belong to the original typed handoff.')
    public, final = progress(result)
    if public != public_plan(data):
        fail('The actual Apply plan differs from the acknowledged ZIP.')
    source_base, files = snapshot(source)
    for stage in data['stages'][:len(final['committed'])]:
        files = apply_stage(files, stage)
    base, work = snapshot(result)
    committed_files = files if final['committed'] else source_base
    if base != committed_files or result['success'] and work != files:
        fail('Result snapshot differs from the tested committed stage prefix.')
    if result['success']:
        completion(result, data)
    rest = data['stages'][len(final['committed']):]
    return {'verified': True, 'pending_clarification': bool(not result['success'] and rest and rest[0]['role'] == 'clarification')}


def guarded(function, *args):
    try:
        return function(*args)
    except ControlError:
        raise
    except (OSError, ValueError, TypeError, KeyError, IndexError, SyntaxError, RecursionError,
            zipfile.BadZipFile, zlib.error, RuntimeError, NotImplementedError, OverflowError):
        fail('Missing, changed or malformed typed bundle evidence.')


def verify_handoff(engine, source, patch, selected, status):
    return guarded(handoff, engine, source, patch, selected, status)


def verify_followup(engine, source, patch_sha, result, output_kind):
    return guarded(followup, engine, source, patch_sha, result, output_kind)
