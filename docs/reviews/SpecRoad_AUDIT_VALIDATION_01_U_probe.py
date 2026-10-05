"""Historical parallel observations for AUDIT-VALIDATION-01.U, not regressions.

Only fresh owned temporary projects are written. Observed missing diagnostics
are data, never assertions that a defect must persist after its later repair.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
CASES = ('complete_minima', 'missing_rationale', 'missing_verification',
         'missing_origin', 'missing_both_relations', 'core_placeholder',
         'forbidden_literal', 'draft_missing_rationale_and_relations')


def probe_case(task):
    repository, case = task
    repository = Path(repository)
    sys.path[:0] = [str(repository / 'src'), str(repository / 'tests')]
    from specroad.graph.relation_obligations import RelationObligations
    from specroad.graph.relations import SourceRelations
    from specroad.lint import Glossary, lint_literals
    from specroad.model.domain_schemas import validate_domain_fields
    from specroad.model.errors import ModelError
    from specroad.profiles import ProfileResource
    from specroad.storage.domain_artifact import DomainArtifact
    from specroad.storage.read_only import lint_project_read_only, validate_project_read_only
    from support.artifacts import artifact_bytes
    from support.domain import approved_value, domain_value
    from support.model_validation import edge
    from support.read_only import inventory, literal_policy, make_project, no_write_attempts
    from support.records import record_value

    def observe(function):
        try:
            data = function()
            return {'returned': True, 'data': data}
        except ModelError as error:
            return {'returned': False, 'reason': error.reason,
                    'pointer': error.pointer, 'diagnostic': error.diagnostic()}

    requirement = approved_value('requirement', language='en')
    origin = domain_value('goal')
    verification = record_value('verification', subjects=[requirement['id']])
    term = domain_value('term', language='en')
    requirement['relations'] = [edge(origin, 'addresses', 0), edge(verification, 'verified_by', 1)]
    if case in ('missing_rationale', 'draft_missing_rationale_and_relations'):
        requirement.pop('rationale')
    if case == 'missing_verification':
        requirement['relations'] = requirement['relations'][:1]
    if case == 'missing_origin':
        requirement['relations'] = requirement['relations'][1:]
    if case in ('missing_both_relations', 'draft_missing_rationale_and_relations'):
        requirement['relations'] = []
    if case == 'draft_missing_rationale_and_relations':
        requirement['maturity'] = 'draft'
    if case == 'core_placeholder':
        requirement['statement'] = 'TODO specify the offline behavior.'
    if case == 'forbidden_literal':
        requirement['statement'] = 'The Magic box works offline.'
    values = (requirement, origin, verification, term)
    policy = literal_policy(term_ids=[term['id']])
    glossary = Glossary((DomainArtifact(artifact_bytes(term), expected_type='term'),))
    profile_bytes = (repository / 'src/specroad/profile_data/core.json').read_bytes()
    profile = ProfileResource(profile_bytes)

    def minima():
        result = RelationObligations(tuple(SourceRelations(artifact_bytes(value)) for value in values))
        return {'requirements_satisfied': result.requirements_satisfied,
                'scope': result.validation_scope, 'diagnostics': list(result.diagnostics),
                'checks': [{'rule_id': check.rule_id, 'minimum': check.minimum,
                            'actual': check.actual, 'satisfied': check.satisfied}
                           for check in result.checks]}

    def projection(value):
        data = value.data
        return {key: data[key] for key in (
            'status', 'exit_code', 'passed', 'checks_complete', 'model_loaded',
            'normal_operation_started', 'write_authorized', 'approval_granted',
            'project_complete', 'diagnostics', 'lint', 'validation')}

    with tempfile.TemporaryDirectory(prefix='specroad-audit-validation-01-u-') as temp:
        root = Path(temp)
        make_project(root, *values)
        before = inventory(root)
        inputs = {name: hashlib.sha256(raw).hexdigest()
                  for name, mode, raw, link in before if raw is not None}
        with no_write_attempts() as writes:
            fields = observe(lambda: validate_domain_fields(requirement))
            relation_checks = observe(minima)
            literal = observe(lambda: lint_literals(requirement, glossary=glossary, policy=policy))
            lint = projection(lint_project_read_only(root, policy=policy, selected_ids=(requirement['id'],)))
            strict_lint = projection(lint_project_read_only(
                root, policy=policy, selected_ids=(requirement['id'],), strict=True))
            validation = projection(validate_project_read_only(
                root, profile_resources=(profile,), core_key=profile.key))
        return {'case': case, 'input_file_sha256': inputs,
                'core_profile_sha256': hashlib.sha256(profile_bytes).hexdigest(),
                'write_attempts': len(writes), 'project_inventory_unchanged': inventory(root) == before,
                'domain_fields': fields, 'minimum_relations': relation_checks,
                'literal_api': literal, 'public_lint': lint,
                'public_lint_strict': strict_lint, 'public_validation': validation}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repository', type=Path)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    if args.workers < 2:
        parser.error('This audit uses parallel case execution only.')
    repository = args.repository.resolve(strict=True)
    with ProcessPoolExecutor(max_workers=args.workers,
                             mp_context=multiprocessing.get_context('spawn')) as pool:
        observations = list(pool.map(probe_case, ((str(repository), case) for case in CASES)))
    print(json.dumps({'audit': 'AUDIT-VALIDATION-01.U', 'workers': args.workers,
                      'cases': observations}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
