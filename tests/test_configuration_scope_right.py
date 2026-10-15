"""Configured page contracts and required dependency failures over real closures."""
from dataclasses import replace
import pytest

from specroad.graph.closure_inputs import ClosureBindings, artifact_node
from specroad.graph.scope_admission import ScopeConfigurationDependencyError
from specroad.graph.scope_closure import resolve_scope_closure, require_scope_closure_current
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_hash import fingerprint_scope
from specroad.graph.scope_query_page import QuerySeedPage
from specroad.graph.scope_seeds import resolve_scope_seeds
from specroad.graph.strong_closure import resolve_strong_closure
from specroad.model.canonical import canonical_json_sha256
from specroad.model.configuration import ProjectConfiguration
from specroad.model.errors import ModelError
from specroad.model.model_manifest import ProjectReadBinding
from support.closure import observe, source, subject, slot
from support.model import configuration_value
from support.records import record_value
from support.relations import aid, artifact, edge, rid
from support.scopes import descriptor, inputs, query
from support.srx import binary, expression_document, field, literal


def configuration(number=1, **changes):
    return record_value('configuration', id=aid('configuration', number), name='Variant ' + str(number), **changes)


def condition(value):
    return expression_document(binary('eq', field('/effective_values/platform', 'configuration'), literal(value)))


def selected(inventory, ids=None, *, policy='closed', config=aid('configuration')):
    value = descriptor('explicit', {'artifact_ids': sorted([aid()] if ids is None else ids), 'resource_ids': []},
                       configuration_id=config, boundary_policy=policy)
    return resolve_scope_seeds(ScopeDescriptor(value), inventory)


def query_descriptor(*, wrapper=False, config=aid('configuration'), **changes):
    base = descriptor('query', {'query': query(**changes)})
    value = (descriptor('configuration', {'base_scope_descriptor': base}, configuration_id=config)
             if wrapper else {**base, 'configuration_id': config})
    return ScopeDescriptor(value)


PAIRS = [('addresses', 'requirement', 'goal'), ('refines', 'requirement', 'requirement'),
         ('derived_from', 'requirement', 'source'), ('depends_on', 'requirement', 'requirement'),
         ('constrains', 'requirement', 'component'), ('allocated_to', 'requirement', 'interface'),
         ('implemented_by', 'requirement', 'task'), ('verified_by', 'requirement', 'test'),
         ('produces', 'test', 'evidence'), ('mitigates', 'requirement', 'risk'),
         ('scheduled_for', 'requirement', 'release'), ('part_of', 'task', 'release'),
         ('supersedes', 'requirement', 'requirement'), ('contains', 'document', 'section'),
         ('references', 'source', 'requirement')]


@pytest.mark.parametrize('kind,source_type,target_type', PAIRS, ids=[p[0] for p in PAIRS])
@pytest.mark.parametrize('policy', ['closed', 'partial'])
def test_every_strong_relation_rejects_an_excluded_target(kind, source_type, target_type, policy):
    first = source(source_type, relations=[edge(kind, aid(target_type, 2))])
    changes = {'subjects': [subject(first['id'])]} if target_type == 'evidence' else {}
    last = source(target_type, 2, applicability=condition('windows'), **changes)
    inventory = inputs(configuration(), first, last)
    original = tuple(r.source_bytes for r in inventory.records)
    with pytest.raises(ScopeConfigurationDependencyError) as caught:
        resolve_scope_closure(selected(inventory, [first['id']], policy=policy), observe(inventory))
    error = caught.value
    assert (error.source_id, error.target_id, error.relation_id) == (first['id'], last['id'], rid())
    assert error.pointer == '/relations/0/target'
    assert error.code == 'SRV141' and error.exit_code == 3
    assert error.diagnostic()['configuration_id'] == aid('configuration')
    assert tuple(r.source_bytes for r in inventory.records) == original


@pytest.mark.parametrize('kind', ['conflicts_with', 'duplicates'])
def test_closed_weak_relation_also_checks_applicability(kind):
    inventory = inputs(configuration(), artifact(relations=[edge(kind, aid(number=2))]),
                       artifact(number=2, applicability=condition('windows')))
    with pytest.raises(ScopeConfigurationDependencyError):
        resolve_scope_closure(selected(inventory), observe(inventory))


@pytest.mark.parametrize('kind', ['conflicts_with', 'duplicates'])
def test_partial_weak_relation_preserves_the_origin_boundary(kind):
    last = artifact(number=2, applicability=condition('windows'))
    inventory = inputs(configuration(), artifact(relations=[edge(kind, last['id'])]), last)
    closure = resolve_scope_closure(selected(inventory, policy='partial'), observe(inventory))
    assert closure.artifact_ids == (aid(),)
    assert len(closure.boundary_references) == 1
    boundary = closure.boundary_references[0].data
    assert boundary['target_id'] == last['id']
    assert boundary['origin_target_sha256'] == canonical_json_sha256(last)


def test_strong_only_api_keeps_excluded_weak_edge_pending():
    inventory = inputs(configuration(), artifact(relations=[edge('conflicts_with', aid(number=2))]),
                       artifact(number=2, applicability=condition('windows')))
    closure = resolve_strong_closure(selected(inventory), observe(inventory))
    assert closure.artifact_ids == (aid(),)
    assert closure.pending_weak_relations == ((aid(), rid(), aid(number=2)),)


@pytest.mark.parametrize('policy', ['closed', 'partial'])
def test_contract_test_slot_is_a_required_dependency(policy):
    contract = source('verification', evidence_slots=[slot(aid('test'))])
    inventory = inputs(configuration(), contract, artifact('test', applicability=condition('windows')))
    with pytest.raises(ScopeConfigurationDependencyError) as caught:
        resolve_scope_closure(selected(inventory, [contract['id']], policy=policy), observe(inventory))
    assert caught.value.pointer == '/evidence_slots/0/test_id'
    assert caught.value.source_id == contract['id']
    assert caught.value.target_id == aid('test')
    assert caught.value.relation_id is None


@pytest.mark.parametrize('policy', ['closed', 'partial'])
def test_selected_current_relation_review_is_a_required_dependency(policy):
    review = source('relation_review', relation_id=rid(), applicability=condition('windows'))
    inventory = inputs(configuration(), artifact(relations=[edge('depends_on', aid(number=2))]),
                       artifact(number=2), review)
    bindings = observe(inventory, reviews={rid(): [review['id']]})
    with pytest.raises(ScopeConfigurationDependencyError) as caught:
        resolve_scope_closure(selected(inventory, policy=policy), bindings)
    assert caught.value.target_id == review['id']
    assert caught.value.relation_id == rid()
    assert caught.value.pointer == '/current_reviews/' + rid() + '/0'


def test_unselected_historical_review_is_not_an_implicit_dependency():
    review = source('relation_review', relation_id=rid(), applicability=condition('windows'))
    inventory = inputs(configuration(), artifact(relations=[edge('depends_on', aid(number=2))]),
                       artifact(number=2), review)
    assert resolve_scope_closure(selected(inventory), observe(inventory)).artifact_ids == (aid(), aid(number=2))


def test_excluded_dependency_is_diagnosed_before_its_usage_provider_is_required():
    inventory = inputs(configuration(), artifact(relations=[edge('depends_on', aid(number=2))]),
                       artifact(number=2, applicability=condition('windows')))
    bindings = observe(inventory)
    uses = dict(bindings.uses); del uses[artifact_node(aid(number=2))]
    bindings = ClosureBindings(inventory, uses=uses, current_reviews=dict(bindings.current_reviews))
    with pytest.raises(ScopeConfigurationDependencyError):
        resolve_scope_closure(selected(inventory), bindings)


@pytest.mark.parametrize('walker', [resolve_scope_closure, resolve_strong_closure], ids=['scope', 'strong'])
def test_transitive_failure_identifies_the_actual_excluded_edge(walker):
    length = 180
    records = [artifact(number=n, relations=[edge('depends_on', aid(number=n + 1), number=n)])
               for n in range(1, length)]
    records.append(artifact(number=length, applicability=condition('windows')))
    inventory = inputs(configuration(), *records)
    with pytest.raises(ScopeConfigurationDependencyError) as caught:
        walker(selected(inventory), observe(inventory))
    assert caught.value.source_id == aid(number=length - 1)
    assert caught.value.target_id == aid(number=length)
    assert caught.value.relation_id == rid(length - 1)


def test_required_cycle_of_applicable_artifacts_terminates_without_losing_members():
    inventory = inputs(configuration(), artifact(relations=[edge('depends_on', aid(number=2))]),
                       artifact(number=2, relations=[edge('depends_on', aid(), number=2)],
                                applicability=condition('linux')))
    result = resolve_scope_closure(selected(inventory), observe(inventory))
    assert result.artifact_ids == (aid(), aid(number=2))
    assert len(result.processing_order) == 2


def test_error_uses_relation_identity_order_but_preserves_original_pointer():
    excluded = [artifact(number=n, applicability=condition('windows')) for n in (2, 3)]
    links = [edge('depends_on', aid(number=3), number=2), edge('depends_on', aid(number=2), number=1)]
    for reverse in (False, True):
        inventory = inputs(configuration(), artifact(relations=links[::-1] if reverse else links), *excluded)
        with pytest.raises(ScopeConfigurationDependencyError) as caught:
            resolve_scope_closure(selected(inventory), observe(inventory))
        assert caught.value.relation_id == rid()
        assert caught.value.target_id == aid(number=2)
        assert caught.value.pointer == ('/relations/0/target' if reverse else '/relations/1/target')


def test_source_enumeration_does_not_change_error_projection():
    records = [configuration(), artifact(relations=[edge('depends_on', aid(number=2))]),
               artifact(number=2, applicability=condition('windows'))]
    diagnostics = []
    for values in (records, records[::-1]):
        inventory = inputs(*values)
        with pytest.raises(ScopeConfigurationDependencyError) as caught:
            resolve_scope_closure(selected(inventory), observe(inventory))
        diagnostics.append(caught.value.diagnostic())
    assert diagnostics[0] == diagnostics[1]
    diagnostics[0]['target_id'] = 'changed'
    assert caught.value.diagnostic()['target_id'] == aid(number=2)


@pytest.mark.parametrize('maturity', ['rejected', 'retired'])
def test_maturity_does_not_override_applicability(maturity):
    values = [configuration(), artifact(relations=[edge('depends_on', aid(number=2))])]
    included = inputs(*values, artifact(number=2, maturity=maturity, applicability=condition('linux')))
    assert aid(number=2) in resolve_scope_closure(selected(included), observe(included)).artifact_ids
    excluded = inputs(*values, artifact(number=2, maturity=maturity, applicability=condition('windows')))
    with pytest.raises(ScopeConfigurationDependencyError):
        resolve_scope_closure(selected(excluded), observe(excluded))


def test_invalid_dependency_condition_is_not_silently_excluded():
    inventory = inputs(configuration(), artifact(relations=[edge('depends_on', aid(number=2))]),
                       artifact(number=2, applicability=expression_document(literal('false'))))
    with pytest.raises(ModelError) as caught:
        resolve_scope_closure(selected(inventory), observe(inventory))
    assert caught.value.reason == 'invalid_applicability'


def test_old_success_cannot_hide_a_new_configuration_conflict_or_supply_a_model_root():
    first = inputs(configuration(), artifact(relations=[edge('depends_on', aid(number=2))]), artifact(number=2))
    old = resolve_scope_closure(selected(first), observe(first))
    second = inputs(configuration(), artifact(relations=[edge('depends_on', aid(number=2))]),
                    artifact(number=2, applicability=condition('windows')))
    seeds, bindings = selected(second), observe(second)
    with pytest.raises(ScopeConfigurationDependencyError):
        require_scope_closure_current(old, seeds, bindings)
    forged = replace(old, seeds=seeds, bindings_sha256=bindings.fingerprint)
    project = ProjectConfiguration(configuration_value())
    with pytest.raises(ScopeConfigurationDependencyError):
        fingerprint_scope(project, ProjectReadBinding(project.project_id, '/owned/synthetic', (1, 2)),
                          forged, bindings, effective_profile={})


@pytest.mark.parametrize('wrapper', [False, True], ids=['direct', 'wrapper'])
def test_configured_query_preserves_the_bound_page_order_and_exact_membership(wrapper):
    inventory = inputs(configuration(), artifact(), artifact(number=2, applicability=condition('windows')),
                       artifact(number=3, applicability=condition('linux')))
    desc = query_descriptor(wrapper=wrapper, limit=2, sort=[{'key': 'id', 'direction': 'desc'}])
    page = QuerySeedPage(desc, inventory, [aid(number=3), aid()], total=2)
    seeds = resolve_scope_seeds(desc, inventory, query_page=page)
    assert seeds.artifact_ids == (aid(number=3), aid())
    assert seeds.canonical_artifact_ids == (aid(), aid(number=3))
    assert seeds.configuration_sha256 == selected(inventory).configuration_sha256
    closure = resolve_scope_closure(seeds, observe(inventory), query_page=page)
    assert closure.artifact_ids == (aid(), aid(number=3))


@pytest.mark.parametrize('wrapper', [False, True], ids=['direct', 'wrapper'])
@pytest.mark.parametrize('offset,limit,ids,total', [(1, 1, [aid(number=3)], 2), (3, 2, [], 2), (0, 0, [], 2)])
def test_configured_query_does_not_fill_or_repaginate_a_supplied_page(wrapper, offset, limit, ids, total):
    inventory = inputs(configuration(), artifact(), artifact(number=2, applicability=condition('windows')),
                       artifact(number=3))
    desc = query_descriptor(wrapper=wrapper, offset=offset, limit=limit)
    page = QuerySeedPage(desc, inventory, ids, total=total)
    assert resolve_scope_seeds(desc, inventory, query_page=page).artifact_ids == tuple(ids)


@pytest.mark.parametrize('wrapper', [False, True], ids=['direct', 'wrapper'])
def test_query_page_rejects_an_excluded_item_instead_of_silently_shortening_the_page(wrapper):
    inventory = inputs(configuration(), artifact(applicability=condition('windows')))
    with pytest.raises(ModelError) as caught:
        QuerySeedPage(query_descriptor(wrapper=wrapper), inventory, [aid()], total=1)
    assert caught.value.reason == 'query_seed_configuration_excluded'


def test_query_total_cannot_exceed_the_applicable_inventory_even_for_an_empty_page():
    inventory = inputs(configuration(), artifact(applicability=condition('windows')))
    with pytest.raises(ModelError) as caught:
        QuerySeedPage(query_descriptor(limit=0), inventory, [], total=2)
    assert caught.value.reason == 'query_seed_pagination_mismatch'


def test_invalid_applicability_in_query_inventory_is_not_lost_by_pagination():
    inventory = inputs(configuration(), artifact(applicability=expression_document(literal('false'))))
    with pytest.raises(ModelError) as caught:
        QuerySeedPage(query_descriptor(limit=0), inventory, [], total=0)
    assert caught.value.reason == 'invalid_applicability'


def test_query_page_uses_inherited_effective_selection():
    root = configuration()
    child = configuration(2, parent=root['id'], dimensions=[], selection={'platform': 'windows'})
    inventory = inputs(root, child, artifact(applicability=condition('windows')))
    desc = query_descriptor(config=child['id'])
    page = QuerySeedPage(desc, inventory, [aid()], total=1)
    assert resolve_scope_seeds(desc, inventory, query_page=page).artifact_ids == (aid(),)


@pytest.mark.parametrize('change', ['configuration', 'source', 'descriptor'])
def test_query_page_binding_rejects_changed_inputs(change):
    inventory = inputs(configuration(), artifact())
    desc = query_descriptor()
    page = QuerySeedPage(desc, inventory, [aid()], total=1)
    if change == 'configuration':
        inventory = inputs(configuration(revision=2), artifact())
    elif change == 'source':
        inventory = inputs(configuration(), artifact(revision=2))
    else:
        desc = query_descriptor(limit=50)
    with pytest.raises(ModelError) as caught:
        resolve_scope_seeds(desc, inventory, query_page=page)
    assert caught.value.reason == 'stale_query_seed_page'


@pytest.mark.parametrize('wrapper', [False, True], ids=['direct', 'wrapper'])
def test_query_requires_the_full_selected_descriptor_binding(wrapper):
    inventory = inputs(configuration(), artifact())
    unconfigured = query_descriptor(config=None)
    page = QuerySeedPage(unconfigured, inventory, [aid()], total=1)
    with pytest.raises(ModelError) as caught:
        resolve_scope_seeds(query_descriptor(wrapper=wrapper), inventory, query_page=page)
    assert caught.value.reason == 'stale_query_seed_page'


@pytest.mark.parametrize('field_name,value,reason', [
    ('artifact_ids', (aid(number=2),), 'query_seed_configuration_excluded'),
    ('total', True, 'query_seed_pagination_mismatch'),
    ('artifact_ids', (aid(), aid()), 'duplicate_query_seed')])
def test_seed_resolver_revalidates_supplied_page_fields(field_name, value, reason):
    inventory = inputs(configuration(), artifact(), artifact(number=2, applicability=condition('windows')))
    desc = query_descriptor()
    page = QuerySeedPage(desc, inventory, [aid()], total=1)
    object.__setattr__(page, field_name, value)
    with pytest.raises(ModelError) as caught:
        resolve_scope_seeds(desc, inventory, query_page=page)
    assert caught.value.reason == reason


def test_a_configured_query_cannot_turn_an_excluded_strong_target_into_a_boundary():
    inventory = inputs(configuration(), artifact(relations=[edge('depends_on', aid(number=2))]),
                       artifact(number=2, applicability=condition('windows')))
    desc = ScopeDescriptor({**query_descriptor().data, 'boundary_policy': 'partial'})
    page = QuerySeedPage(desc, inventory, [aid()], total=1)
    seeds = resolve_scope_seeds(desc, inventory, query_page=page)
    with pytest.raises(ScopeConfigurationDependencyError):
        resolve_scope_closure(seeds, observe(inventory), query_page=page)


def test_configured_query_has_a_revalidated_semantic_model_root():
    inventory = inputs(configuration(), artifact())
    desc = query_descriptor(wrapper=True)
    page = QuerySeedPage(desc, inventory, [aid()], total=1)
    seeds = resolve_scope_seeds(desc, inventory, query_page=page)
    bindings = observe(inventory)
    closure = resolve_scope_closure(seeds, bindings, query_page=page)
    project = ProjectConfiguration(configuration_value())
    manifest = fingerprint_scope(project, ProjectReadBinding(project.project_id, '/owned/synthetic', (1, 2)),
                                closure, bindings, effective_profile={}, query_page=page)
    assert manifest.data['configuration_sha256'] == seeds.configuration_sha256
    with pytest.raises(ModelError) as caught:
        fingerprint_scope(project, ProjectReadBinding(project.project_id, '/owned/synthetic', (1, 2)),
                          closure, bindings, effective_profile={})
    assert caught.value.reason == 'bound_query_seed_page_required'
