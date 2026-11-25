"""Keep intermediate resource observations distinct from final acceptance.

This module only reads existing evidence. It never starts a measurement,
transfers an old build's observations, or grants a product release.
"""
from pathlib import Path
import re

from .records import object_bytes, require
from .verify import check

POLICY_PATH = 'verification/resource_measurement_policy.json'
PLAN_PATH = 'docs/implementation/SpecRoad_Implementierungsplan.md'
POLICY = {
    'format_version': 1,
    'policy_id': 'RESOURCE-FINAL-809',
    'scope': 'analyzer_total_process_cpu_rss',
    'intermediate_builds': 'deferred',
    'final_plan_group': '20.n',
    'final_obligation': 'required_for_exact_final_build',
    'obsolete_intermediate_builds': 'no_retrospective_measurement',
}


def final_required(root, *, commit_id=None, final=False):
    """The final stage or a completed plan cannot inherit development deferral."""
    policy = object_bytes((Path(root) / POLICY_PATH).read_bytes())
    require(type(policy.get('format_version')) is int and policy == POLICY,
            'invalid_resource_measurement_policy')
    require(type(final) is bool, 'invalid_final_request')
    require(commit_id is None or type(commit_id) is str and bool(commit_id),
            'invalid_resource_commit_id')
    text = (Path(root) / PLAN_PATH).read_text(encoding='utf-8')
    blocks = re.findall(r'^```yaml\n(.*?)^```$', text, re.M | re.S)
    require(len(blocks) == 1, 'ambiguous_plan_progress')
    keys = ('implementation_state', 'implementation_plan_commits_completed',
            'implementation_plan_commits_total', 'last_completed_plan_commit')
    progress = {}
    for key in keys:
        values = re.findall(r'^' + key + r': ([^\n]+)$', blocks[0], re.M)
        require(len(values) == 1, 'missing_or_duplicate_plan_progress')
        progress[key] = values[0]
    completed = progress['implementation_plan_commits_completed']
    total = progress['implementation_plan_commits_total']
    require(re.fullmatch(r'0|[1-9][0-9]*', completed) is not None
            and re.fullmatch(r'[1-9][0-9]*', total) is not None
            and int(completed) <= int(total), 'invalid_plan_counts')
    require(progress['implementation_state'] in ('in_progress', 'complete', 'completed'),
            'unknown_implementation_state')
    last = progress['last_completed_plan_commit']
    require(re.fullmatch(r'[0-9]+\.[a-z]+(?:[1-9][0-9]*)?\.[WRC]', last) is not None,
            'invalid_last_plan_commit')
    return (final or (commit_id or '').startswith('20.n.')
            or last.startswith('20.n.') or int(completed) == int(total)
            or progress['implementation_state'] != 'in_progress')


def evaluate(root, *, expected_build, commit_id=None, final=False):
    """Return an honest obligation status, separately from measured status."""
    require(type(expected_build) is str
            and re.fullmatch(r'[0-9a-f]{64}', expected_build) is not None,
            'invalid_expected_build')
    required = final_required(root, commit_id=commit_id, final=final)
    directory = Path(root) / 'verification/fixtures/analyzer-resources-builds' / expected_build
    exists = directory.exists() or directory.is_symlink()
    measurement = check(directory, expected_build=expected_build) if exists else None
    measured = 'missing' if measurement is None else measurement['status']
    # An invalid supplied proof is never hidden by deferral. Valid measured
    # failures remain visible; optimization is due at final acceptance.
    if measured == 'blocked':
        status = 'blocked'
    elif not required:
        status = 'deferred'
    else:
        status = 'blocked' if measured == 'missing' else measured
    return {
        'format_version': 1, 'policy_id': POLICY['policy_id'],
        'status': status, 'expected_build_sha256': expected_build,
        'measurement_status': measured, 'measurement': measurement,
        'final_required': required,
        'final_obligation': 'satisfied' if required and status == 'passed' else 'pending',
        'release_approved': False, 'human_corpus_review_completed': False,
    }
