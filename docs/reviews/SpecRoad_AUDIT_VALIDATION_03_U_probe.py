"""Historical parallel observations of reference diagnostic completeness.

No assertions preserve missing findings as desired behavior. Fresh owned project
fixtures and real public validators are used without supplied semantic gates.
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
CASES = ('valid_closed_graph', 'missing_targets_two_sources',
         'missing_targets_same_source', 'same_missing_target_twice',
         'missing_and_wrong_type', 'missing_field_targets',
         'missing_relation_and_field_targets', 'two_parse_errors',
         'two_schema_errors', 'two_unknown_selected_ids',
         'selected_missing_targets', 'unreadable_target_blocks_references')


def probe_case(task):
    repository, case = task
    repository = Path(repository)
    sys.path[:0] = [str(repository / 'src'), str(repository / 'tests')]
    from specroad.diagnostics import Diagnostic, assess_diagnostics
    from specroad.graph.references import RelationReferences
    from specroad.graph.relations import SourceRelations
    from specroad.model.errors import ModelError
    from specroad.model.paths import artifact_path
    from specroad.profiles import compose_profiles
    from specroad.storage.profiles import load_bundled_profile
    from specroad.storage.read_only import validate_project_read_only
    from specroad.validation import ModelDocument, validate_model, assess_validation
    from support.model_validation import artifact, edge
    from support.read_only import inventory, make_project, no_write_attempts

    def path(value):
        return artifact_path(value['artifact_type'], value['id'], 'SR')

    def observe(function):
        try:
            return {'returned': True, 'data': function()}
        except ModelError as error:
            return {'returned': False, 'reason': error.reason,
                    'pointer': error.pointer, 'diagnostic': error.diagnostic()}

    a, b, c, d = [artifact(number=n) for n in (1, 2, 11, 12)]
    a['relations'] = [edge(c, number=1)]
    b['relations'] = [edge(d, number=2)]
    values, selected, raw_overrides = [a, b], None, {}
    if case in ('valid_closed_graph', 'two_unknown_selected_ids'):
        values += [c, d]
    if case == 'valid_closed_graph':
        components = [artifact('component', number=n) for n in (11, 12)]
        values += [*components, artifact('interface', number=1,
            source_component=components[0]['id'], target_component=components[1]['id'])]
    if case == 'missing_targets_same_source':
        a['relations'].append(edge(d, number=2))
        b['relations'] = []
    if case == 'same_missing_target_twice':
        b['relations'][0]['target'] = c['id']
    if case == 'missing_and_wrong_type':
        component = artifact('component', number=11)
        b['relations'][0]['target'] = component['id']
        values.append(component)
    if case in ('missing_field_targets', 'missing_relation_and_field_targets'):
        interface = artifact('interface', number=1,
            source_component=artifact('component', number=11)['id'],
            target_component=artifact('component', number=12)['id'])
        values = [interface] if case == 'missing_field_targets' else [a, interface]
    if case in ('two_parse_errors', 'two_schema_errors'):
        a['relations'] = b['relations'] = []
        if case == 'two_parse_errors':
            raw_overrides = {path(a): b'{bad', path(b): b'{]'}
        else:
            a.pop('title')
            b.pop('owner')
    if case == 'two_unknown_selected_ids':
        selected = (a['id'], artifact(number=91)['id'], artifact(number=92)['id'])
    if case == 'selected_missing_targets':
        selected = (a['id'],)
    if case == 'unreadable_target_blocks_references':
        values = [a, c]
        raw_overrides = {path(c): b'{bad'}
    core = load_bundled_profile('core@0.2.0')
    profile = compose_profiles((core,), core_key=core.key)

    with tempfile.TemporaryDirectory(prefix='specroad-audit-validation-03-u-') as temp:
        root = Path(temp)
        make_project(root, *values)
        for name, raw in raw_overrides.items():
            (root / name).write_bytes(raw)
        before = inventory(root)
        documents = tuple(ModelDocument(path(v), (root / path(v)).read_bytes()) for v in values)
        with no_write_attempts() as writes:
            report = validate_model(documents, profile=profile, selected_ids=selected)
            direct = assess_validation(report, documents=documents).as_dict()
            reverse = assess_validation(validate_model(documents[::-1], profile=profile,
                selected_ids=selected), documents=documents[::-1]).as_dict()
            public = validate_project_read_only(root, profile_resources=(core,),
                core_key=core.key, selected_ids=selected).data

            def graph():
                refs = RelationReferences(tuple(SourceRelations(d.content, path=d.path) for d in documents))
                return {'source_count': len(refs.sources), 'relation_count': len(refs.relations),
                        'validation_scope': refs.validation_scope}

            graph_result = observe(graph)
            isolated = []
            merged = None
            independent_type_error = None
            if case in ('missing_targets_two_sources', 'same_missing_target_twice'):
                # Each original source still references a target absent from the
                # whole fixture. These are separate inputs, not a whole-model pass.
                for document in documents:
                    one = assess_validation(validate_model((document,), profile=profile),
                                            documents=(document,)).as_dict()
                    isolated.append({'source_path': document.path, 'assessment': one})
                merged = assess_diagnostics(
                    [Diagnostic.from_dict(item) for result in isolated
                     for item in result['assessment']['diagnostics']],
                    checked_ids=[v['id'] for v in values], complete=False,
                    operational_exit_code=3).as_dict()
            if case == 'missing_and_wrong_type':
                # Preserve the second original source and its loaded endpoint;
                # exclude only the first source that otherwise stops discovery.
                subset = tuple(d for d in documents if d.path != path(a))
                independent_type_error = assess_validation(validate_model(subset, profile=profile),
                                                          documents=subset).as_dict()
        return {'case': case, 'fixture_artifacts_before_raw_overrides': values,
                'raw_overrides': {name: raw.decode('utf-8') for name, raw in raw_overrides.items()},
                'requested_ids': selected, 'core_profile_sha256': core.source_sha256,
                'input_file_sha256': {name: hashlib.sha256(raw).hexdigest()
                    for name, mode, raw, link in before if raw is not None},
                'write_attempts': len(writes), 'project_inventory_unchanged': inventory(root) == before,
                'direct_model_assessment': direct,
                'reversed_document_order_same_assessment': direct == reverse,
                'public_validation': public, 'graph_constructor': graph_result,
                'isolated_source_assessments': isolated, 'merged_observed_diagnostics': merged,
                'independent_type_error': independent_type_error}


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
    print(json.dumps({'audit': 'AUDIT-VALIDATION-03.U', 'workers': args.workers,
                      'cases': observations}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
