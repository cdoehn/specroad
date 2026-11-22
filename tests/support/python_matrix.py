"""Shared actual-interpreter jobs and separate sandbox/host evidence; no new oracle."""
from hashlib import sha256
import json
from support.network_isolation import NETWORK_ISOLATION
from support.security_boundary import CORE_GUARD
from support.processes import run_python

MINORS = ('3.10', '3.11', '3.12', '3.13', '3.14')

def runtime_prefix(row, minor):
    return ('import sys,os,platform\n'
        + 'assert sys.implementation.name == "cpython"\n'
        + 'assert platform.python_version() == ' + repr(row['version']) + '\n'
        + 'assert ".".join(map(str,sys.version_info[:2])) == ' + repr(minor) + '\n'
        + 'assert sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode\n'
        + 'assert "VIRTUAL_ENV" not in os.environ and "PYTHONPATH" not in os.environ\n'
        + 'assert not any("site-packages" in p or "dist-packages" in p for p in sys.path)\n')

def fresh_cli(row, minor, distribution, cwd, arguments):
    body = (NETWORK_ISOLATION + runtime_prefix(row, minor) + CORE_GUARD
        + 'import runpy\nsys.argv = ' + repr([str(distribution), *arguments]) + '\n'
        + 'runpy.run_path(sys.argv[0], run_name="__main__")\n')
    return run_python(['-I', '-S', '-B', '-c', body], cwd,
                      python=row['executable'], capture=True)

def runtime_evidence(row, minor, distribution, cwd):
    body = (NETWORK_ISOLATION + runtime_prefix(row, minor) + CORE_GUARD
        + 'import json\nsys.path.insert(0, ' + repr(str(distribution)) + ')\n'
        + 'from specroad.runtime.identity import version_info\n'
        + 'print(json.dumps({"runtime": version_info(), "isolation": network_isolation, '
        + '"uid": os.geteuid(), "site_enabled": not bool(sys.flags.no_site)}))\n')
    result = run_python(['-I', '-S', '-B', '-c', body], cwd,
                        python=row['executable'], capture=True)
    assert result.returncode == 0, result.stderr
    value = json.loads(result.stdout)
    value['executable_sha256'] = row['sha256']
    return value

REVIEW_PROGRAM = r'''
from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.changes import PublicationAuthority
from specroad.proposals import ProposalOriginal, ProposalContext
from specroad.proposals.review_start import review_start_project
from specroad.proposals.apply import apply_project
from specroad.proposals.scope import specification_manifest
from support.proposal_decisions import ReviewCase
model = InspectionSnapshot(root, None).model
original = ProposalOriginal(model.source_files[proposal_path], path=proposal_path)
case = ReviewCase.__new__(ReviewCase)
case.root = root; case.originals = [original]; case.contexts = [ProposalContext(original, model)]
case.reviews = []; case.controls = []; case.current_decisions = True
case.authority = PublicationAuthority('synthetic-python-matrix-host', '1', lambda request: True)
review_start_project(root, original.data['id'], expected_revision=1,
    actor={'actor_type':'human','actor_id':'synthetic-author'}, planned_at='2026-11-18T01:00:00Z',
    change_plan_id='matrix-start', transaction_id='matrix-start', authority=case.authority)
case.capture(start=True)
case.decide(planned_at='2026-11-18T01:30:00Z')
options = dict(expected_revision=case.original.data['revision'],
    actor={'actor_type':'human','actor_id':'synthetic-applier'}, planned_at='2026-11-18T02:00:00Z',
    change_plan_id='matrix-apply', transaction_id='matrix-apply', request_id='matrix-apply',
    authority=case.authority, services=case.services)
def inventory():
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}
before = inventory()
dry = apply_project(root, original.data['id'], dry_run=True, **options)
assert dry['dry_run'] and inventory() == before
applied = apply_project(root, original.data['id'], **options)
assert applied['proposal_status'] == 'applied' and applied['completion'] is not None
final = InspectionSnapshot(root, None).model
assert specification_manifest(final).sha256 == expected_target
assert next(a for a in final.artifacts if a['artifact_type']=='goal')['statement'] == 'Native proposed change'
assert next(a for a in final.artifacts if a['id']==original.data['id'])['proposal_status'] == 'applied'
print(json.dumps({'runtime': sys.version.split()[0], 'target_sha256': specification_manifest(final).sha256,
    'dry_run_preserved_bytes': True, 'proposal_status': applied['proposal_status']}))
'''


def fresh_request(row, minor, source, cwd, value):
    program = (NETWORK_ISOLATION + runtime_prefix(row, minor) + CORE_GUARD
        + 'import json\nsys.path.insert(0,' + repr(str(source)) + ')\n'
        + 'from specroad.cli.application import execute_request\n'
        + 'result=execute_request(' + repr(value) + ').result\n'
        + 'print(json.dumps(result.as_dict()))\n')
    child = run_python(['-I', '-S', '-B', '-c', program], cwd,
                       python=row['executable'], capture=True)
    assert child.returncode == 0, child.stderr
    return json.loads(child.stdout)
