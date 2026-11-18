"""Passive native Proposal execution; Work completion is never approval."""
from ..authoring._inspection_snapshot import InspectionSnapshot
from ..cli.requests import CommandRequest
from ..migration.plan_values import file_bindings
from ..model.canonical import canonical_json_bytes as jcs
from ..proposals._check_workspace import CheckWorkspace
from ..proposals._validation_input import ProposalInput
from ..proposals.check import check_proposal_project
from ..proposals.project_validation import _preflight
from ..proposals.scope import specification_manifest
from ..storage.project import ProjectSource
from ._request_binding import _command
from .manifest import _create_manifest, partition_work_manifest, complete_work_manifest
from .resume import _runtime_build
from .control import _initial
from ._completion import read_completion
from ._proposal_contract import ADAPTER, _units, _block, _report, _semantic, checked, require


def prepare_proposal_work(registry, root, operand, *, cwd=None):
    """Seal coherent complete input bytes before allocating any Work directory."""
    source = ProjectSource(root); _preflight(source)
    supplied = ProposalInput(source, operand, cwd)
    original = supplied.original()
    snapshot = InspectionSnapshot(root, None, include_archive_objects=True)
    basis_hash = specification_manifest(snapshot.model).sha256
    require(basis_hash == original.binding.base_model_root_sha256, 'proposal_work_basis_changed')
    resources = {'basis': file_bindings(snapshot.raw),
                 'proposal': file_bindings({original.path: original.source_bytes})}
    descriptor = dict(adapter=ADAPTER, project_id=source.configuration.project_id,
        basis_sha256=basis_hash, proposal_path=original.path, binding=original.binding.data,
        proposal_sha256=original.sha256, resources=resources)
    inputs = [{'root_id': 'basis', 'path': p, 'raw': b} for p, b in sorted(snapshot.raw.items())]
    inputs.extend(({'root_id': 'proposal', 'path': original.path, 'raw': original.source_bytes},
                   {'root_id': 'control', 'path': 'request.json', 'raw': jcs(descriptor)}))
    command = _command(registry, CommandRequest('proposal.check', arguments={'proposal': original.data['id']}))
    initial = _create_manifest(registry, command, tool_build=_runtime_build(),
        source_bindings={'project_id': descriptor['project_id'], 'scope': ['specification'],
                         'model_root_sha256': basis_hash}, inputs=inputs, units=_units(resources))
    _preflight(source); source.check_current(); supplied.verify_current(); snapshot.verify_current()
    return initial, (source.boundary, supplied.boundary)


def _calculate(store, descriptor, rows, services):
    workspace = CheckWorkspace(store._location.path, False, guard=store._location._outside)
    try:
        workspace.create()
        files = {path: raw for (kind, path), raw in rows.items() if kind == 'basis'}
        root = workspace.materialize('basis', files)
        snapshot = InspectionSnapshot(root, None, include_archive_objects=True)
        require(snapshot.raw == files and snapshot.model.configuration.project_id == descriptor['project_id']
            and specification_manifest(snapshot.model).sha256 == descriptor['basis_sha256'],
                'proposal_work_basis_changed')
        operand = workspace.materialize('operand', {'original.json': rows['proposal', descriptor['proposal_path']]})
        result = check_proposal_project(root, str(operand/'original.json'), services=services)
        snapshot.verify_current(); workspace.verify()
        outcome = {'report': result.as_dict()['result'], 'exit_code': result.exit_code}
        _report(outcome)
        require(outcome['report']['binding'] == descriptor['binding']
            and outcome['report']['proposal_sha256'] == descriptor['proposal_sha256'],
                'proposal_work_check_binding_changed')
        return outcome
    finally:
        workspace.close()


def _final(store, descriptor, rows, results, services):
    actual = _calculate(store, descriptor, rows, services)
    require('check' in results and _semantic(actual) == _semantic(results['check']),
            'proposal_work_check_recomputation_mismatch')
    return results['check']  # Preserve the original audit, not a new claimed review.


def resume_proposal_work(store, *, max_units=1, services=None):
    require(type(max_units) is int and max_units > 0, 'proposal_work_units_invalid')
    _initial(store, _runtime_build())
    def advance(current):
        descriptor, rows, tasks, done, results = checked(current)
        if current.as_dict()['state'] == 'completed':
            _completed(store, current, descriptor, rows, results, services)
            return current
        completions = {}
        for task in tasks[len(done):len(done)+max_units]:
            phase = task['phase']
            result = (_block(task, rows) if phase == 'input_integrity' else
                      _calculate(store, descriptor, rows, services) if phase == 'check' else
                      _final(store, descriptor, rows, results, services))
            results[phase] = result
            completions[task['unit_id']] = jcs({'adapter': ADAPTER, 'phase': phase, 'result': result})
        if completions:
            return partition_work_manifest(current, completions)
        final = _final(store, descriptor, rows, results, services)
        require(jcs(final) == jcs(results.get('finalize')), 'proposal_work_final_result_changed')
        return complete_work_manifest(current, final, exit_code=final['exit_code'])
    return store._update(advance)


def check_outcome(value, document, exit_code):
    require(value['command_id'] == 'proposal.check' and value['command_class'] == 'read_only',
            'proposal_work_outcome_invalid')
    _report(document)
    require(type(exit_code) is int and exit_code == document['exit_code'], 'proposal_work_exit_changed')


def _completed(store, current, descriptor, rows, results, services):
    actual = _final(store, descriptor, rows, results, services)
    record = read_completion(current.as_dict(), current.objects, current._registry)
    require(jcs(actual) == jcs(results.get('finalize')) == jcs(record['outcome']),
            'proposal_work_final_result_changed')
    return record


def proposal_work_result(store, *, services=None):
    _initial(store, _runtime_build())
    current = store.read()
    descriptor, rows, _, _, results = checked(current)
    require(current.as_dict()['state'] == 'completed', 'proposal_work_incomplete')
    record = _completed(store, current, descriptor, rows, results, services)
    require(store.read().raw == current.raw, 'proposal_work_delivery_changed')
    return record['outcome']['report'], record['exit_code']
