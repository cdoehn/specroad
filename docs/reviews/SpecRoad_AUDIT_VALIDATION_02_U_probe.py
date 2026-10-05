"""Historical parallel observations for AUDIT-VALIDATION-02.U, not regressions.

Uses real temporary project files and shipped profile/registry bytes. No trusted
success gates, synthetic human approvals, publication backend or product writes.
Missing functionality is recorded, never asserted as behavior to preserve.
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
CASES = ('draft_software_en', 'draft_software_de', 'draft_core',
         'draft_language_disallowed', 'draft_language_warning',
         'draft_registry_missing', 'draft_statement_missing',
         'in_review_complete', 'approved_complete', 'approved_placeholder',
         'approved_verification_subject_mismatch', 'approved_verification_missing')


def probe_case(task):
    repository, case = task
    repository = Path(repository)
    sys.path[:0] = [str(repository / 'src'), str(repository / 'tests')]
    from specroad.changes import TargetModel, TargetPolicy, prepare_change_target, dry_run_change
    from specroad.model.errors import ModelError
    from specroad.model.paths import artifact_path
    from specroad.profiles import compose_profiles
    from specroad.srx import SrxProgram, EvaluationContext, evaluate
    from specroad.storage.language_policy import inspect_requirement_language
    from specroad.storage.language_registry import (bundled_language_registry, registry_binding,
                                                   read_language_registry)
    from specroad.storage.model_root import capture_model_inputs, check_model_inputs_current
    from specroad.storage.profiles import load_bundled_profile, read_profile
    from specroad.storage.project import ProjectSource
    from specroad.storage.read_only import validate_project_read_only
    from specroad.validation import (ModelDocument, validate_model, assess_validation,
                                    ApprovalContext, assess_requirement_approval)
    from support.domain import domain_value, approved_value
    from support.folds import edit
    from support.model import put
    from support.model_validation import edge
    from support.read_only import inventory, make_project, no_write_attempts
    from support.records import record_value
    from support.targets import SCOPE

    def observe(function):
        try:
            return {'returned': True, 'data': function()}
        except ModelError as error:
            return {'returned': False, 'reason': error.reason,
                    'pointer': error.pointer, 'diagnostic': error.diagnostic()}

    requirement = (approved_value('requirement', language='en')
                   if case.startswith('approved_') or case == 'in_review_complete'
                   else domain_value('requirement', language='en'))
    origin = domain_value('goal')
    verification = record_value('verification', subjects=[requirement['id']])
    values = [requirement, origin]
    if case.startswith('approved_') or case == 'in_review_complete':
        requirement['relations'] = [edge(origin, 'addresses', 0), edge(verification, 'verified_by', 1)]
        values.append(verification)
    if case == 'in_review_complete':
        requirement['maturity'] = 'in_review'
    if case in ('draft_language_disallowed', 'draft_language_warning'):
        requirement['language'] = 'de'
    if case == 'draft_statement_missing':
        requirement.pop('statement')
    if case == 'approved_placeholder':
        requirement['statement'] = 'TODO specify the offline behavior.'
    if case == 'approved_verification_subject_mismatch':
        verification['subjects'] = [origin['id']]
    if case == 'approved_verification_missing':
        requirement['relations'] = requirement['relations'][:1]
    profiles = [load_bundled_profile('core@0.2.0')]
    if case != 'draft_core':
        profiles.append(load_bundled_profile(
            'software-de@0.2.0' if case == 'draft_software_de' else 'software-en@0.2.0'))
    registry = bundled_language_registry()
    binding = registry_binding(registry)
    config = {'profiles': [p.key for p in profiles[1:]],
              'language_policy': {'allowed_ranges': ['en'],
                                  'disallowed_language': 'warning' if case == 'draft_language_warning' else 'error'}}
    if case != 'draft_registry_missing':
        config['language_registry'] = binding
    artifact_paths = [artifact_path(value['artifact_type'], value['id'], 'SR') for value in values]
    profile_paths = ['profiles/' + p.profile_id + '.json' for p in profiles]

    with tempfile.TemporaryDirectory(prefix='specroad-audit-validation-02-u-') as temp:
        root = Path(temp)
        make_project(root, *values, **config)
        for path, resource in zip(profile_paths, profiles):
            put(root, path, resource.source_bytes)
        if case != 'draft_registry_missing':
            put(root, binding['path'], registry.source_bytes)
        before = inventory(root)
        inputs = {name: hashlib.sha256(raw).hexdigest()
                  for name, mode, raw, link in before if raw is not None}
        with no_write_attempts() as writes:
            source = ProjectSource(root)
            resources = tuple(read_profile(source, path, expected_key=p.key, expected_sha256=p.sha256)
                              for path, p in zip(profile_paths, profiles))
            documents = tuple(ModelDocument(path, source.read_normative(path)) for path in artifact_paths)
            profile = compose_profiles(resources, core_key=resources[0].key,
                                       project_profiles=config['profiles'])
            public = validate_project_read_only(root, profile_resources=resources, core_key=resources[0].key).data
            public_strict = validate_project_read_only(
                root, profile_resources=resources, core_key=resources[0].key, strict=True).data
            report = validate_model(documents, profile=profile)
            assessment = assess_validation(report, documents=documents).as_dict()
            language = observe(lambda: inspect_requirement_language(source, artifact_paths[0], package_references=()))
            language_strict = observe(lambda: inspect_requirement_language(
                source, artifact_paths[0], package_references=(), strict=True))
            srx = []
            for resource in resources:
                for rule in resource.rules('lint_rules'):
                    program = SrxProgram(rule['definition']['program'], rule_id=rule['rule_id'])
                    context = EvaluationContext({'artifact': requirement, 'configuration': None,
                        'project': source.configuration.data, 'relations': requirement['relations']},
                        rule_id=rule['rule_id'])
                    srx.append({'profile': resource.key, 'rule_id': rule['rule_id'],
                                'rule_sha256': rule['sha256'], 'value': evaluate(program, context)})
            approval = None
            if requirement['maturity'] in ('in_review', 'approved'):
                approval = assess_requirement_approval(ApprovalContext(requirement['id'], documents,
                    profile=profile, configuration=source.configuration.data,
                    mode='stored' if requirement['maturity'] == 'approved' else 'transition')).data

            def target_observation():
                captured = capture_model_inputs(source, (*artifact_paths, *profile_paths))
                observed_registry = (read_language_registry(source)
                                     if case != 'draft_registry_missing' else None)
                bound_profile = compose_profiles(resources, core_key=resources[0].key,
                    project_profiles=config['profiles'],
                    language_registry=observed_registry)
                resource_documents = [ModelDocument(path, source.read_normative(path)) for path in profile_paths]
                if observed_registry is not None:
                    resource_documents.append(ModelDocument(binding['path'], observed_registry.source_bytes))
                model = TargetModel(captured.configuration_bytes, captured.binding, documents,
                                    profile=bound_profile, resource_files=resource_documents)
                policy = TargetPolicy('ordinary-change', '1', ())
                target = prepare_change_target(model, [edit(origin, 'Maintain offline auditability.')],
                    change_plan_id='CP-audit-validation-02', request_id='audit-validation-02',
                    actor={'actor_type': 'human', 'actor_id': 'audit-fixture'},
                    planned_at='2026-10-05T00:00:00Z', scope_descriptor=SCOPE,
                    metadata_policy_version='change-metadata-v1', policy=policy)
                dry = dry_run_change(target.plan, model, policy=policy)
                check_model_inputs_current(source, captured)
                return {'target': target.data, 'dry_run': dry.data,
                        'same_target_assessment': target.data == dry.data['assessment'],
                        'captured_bytes_rechecked': True}

            target = observe(target_observation)
        return {'case': case, 'input_file_sha256': inputs,
                'profiles': [{'key': p.key, 'source_sha256': p.source_sha256} for p in profiles],
                'write_attempts': len(writes), 'project_inventory_unchanged': inventory(root) == before,
                'public_validation': public, 'public_validation_strict': public_strict,
                'direct_model_assessment': assessment,
                'direct_language': language, 'direct_language_strict': language_strict,
                'direct_profile_srx': srx, 'direct_approval': approval,
                'target_and_dry_run': target}


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
    print(json.dumps({'audit': 'AUDIT-VALIDATION-02.U', 'workers': args.workers,
                      'cases': observations}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
