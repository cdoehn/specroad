"""Applied Proposal observations retain profile restrictions, never write authority."""
from copy import deepcopy

import pytest

from specroad.changes.values import ChangeOperation
from specroad.graph.relation_obligations import MinimumRelationRule, RelationObligations
from specroad.graph.relations import SourceRelations
from specroad.model.errors import ModelError
from specroad.profiles import ProfileError, ProfileCompositionError, check_profile_fields, check_composed_fields
from specroad.query.selection import NormalizedQuery, select_query
from specroad.srx import EvaluationContext, SrxProgram, evaluate
from specroad.storage.record_artifact import RecordArtifact
from specroad.validation.production import profile_applies
from support.artifacts import artifact_bytes
from support.profile_composition import profile, composed, lint, relation
from support.profiles import selector, requirement
from support.records import record_value, ref
from support.srx import roots


def proposal(**changes):
    # Native passive record construction, not simulated human approval or receipt.
    data = record_value('proposal', proposal_status='applied', maturity='applied',
                        extensions={'example.choice': 2})
    data.update(changes)
    return RecordArtifact(artifact_bytes(data), expected_type='proposal').data


def scoped(**changes):
    return selector(artifact_types=['proposal'], **changes)


def test_wildcard_fields_remain_enforced_before_and_after_composition():
    resource = profile(required_fields=[scoped(fields=['/rationale'])],
        forbidden_fields=[scoped(fields=['/extensions/example.banned'])],
        allowed_values=[scoped(field='/extensions/example.choice', values=[1, 2])])
    effective = composed(resource)
    for maturity in ('approved', 'applied'):
        original = proposal(maturity=maturity)
        for check, contract in ((check_profile_fields, resource), (check_composed_fields, effective)):
            untouched = deepcopy(original)
            observed = check(contract, original)
            assert observed['field_checks_passed'] and observed['checked_fields'] == 3
            assert not observed['approval_granted']
            assert original == untouched
            for failure in ('required', 'forbidden', 'allowed'):
                value = deepcopy(original)
                if failure == 'required':
                    del value['rationale']
                    expected = ('profile_required_field', '/rationale')
                elif failure == 'forbidden':
                    value['extensions']['example.banned'] = None
                    expected = ('profile_forbidden_field', '/extensions/example.banned')
                else:
                    value['extensions']['example.choice'] = 3
                    expected = ('profile_value_not_allowed', '/extensions/example.choice')
                observed = check(contract, value)
                assert not observed['field_checks_passed']
                assert [(d['reason'], d['pointer']) for d in observed['diagnostics']] == [expected]


def test_explicit_applied_field_scope_selects_only_proposal_state():
    resource = profile(required_fields=[selector(artifact_types=['proposal', 'requirement'],
        maturities=['applied'], fields=['/extensions/example.choice'])])
    effective = composed(resource)
    for check, contract in ((check_profile_fields, resource), (check_composed_fields, effective)):
        assert check(contract, proposal())['checked_fields'] == 1
        assert not check(contract, proposal(extensions={}))['field_checks_passed']
        assert check(contract, proposal(maturity='approved', extensions={}))['checked_fields'] == 0
        assert check(contract, requirement())['checked_fields'] == 0
    for kinds in (['requirement'], ['source', 'evidence']):
        with pytest.raises(ProfileError):
            profile(required_fields=[selector(artifact_types=kinds, maturities=['applied'], fields=['/x'])])
        with pytest.raises(ModelError):
            MinimumRelationRule('sample:minimum', artifact_types=kinds,
                maturities=['applied'], relation_types=['references'])


def test_applied_wildcards_preserve_intersection_and_conflict_rules():
    wildcard = profile('all', allowed_values=[scoped(field='/extensions/example.choice', values=[1, 2])])
    explicit = profile('applied', allowed_values=[scoped(maturities=['applied'],
        field='/extensions/example.choice', values=[2, 3])])
    effective = composed(wildcard, explicit)
    for value, accepted in ((1, False), (2, True), (3, False)):
        assert check_composed_fields(effective, proposal(extensions={'example.choice': value}))['field_checks_passed'] is accepted
    assert check_composed_fields(effective, proposal(maturity='approved', extensions={'example.choice': 1}))['field_checks_passed']
    with pytest.raises(ProfileCompositionError) as caught:
        composed(wildcard, profile('disjoint', allowed_values=[scoped(maturities=['applied'],
            field='/extensions/example.choice', values=[3])]))
    assert caught.value.reason == 'profile_empty_intersection'
    with pytest.raises(ProfileCompositionError) as caught:
        composed(profile('required', required_fields=[scoped(fields=['/rationale'])]),
            profile('forbidden', forbidden_fields=[scoped(maturities=['applied'], fields=['/rationale'])]))
    assert caught.value.reason == 'profile_required_forbidden_conflict'


def test_applied_relation_and_lint_selectors_reach_native_observers():
    minimum = relation(artifact_types=['proposal'], maturities=['applied'],
        relation_types=['references'], endpoint_types=['source'], severity='error')
    rule = {**lint(value=False), 'artifact_types': ['proposal'], 'maturities': ['applied']}
    resource = profile(relation_rules=[minimum], lint_rules=[rule])
    effective = composed(resource)
    applied = proposal()
    for rules in (resource.minimum_relation_rules(), effective.minimum_relation_rules()):
        observed = RelationObligations([SourceRelations(artifact_bytes(applied))], profile_rules=rules)
        assert len(observed.checks) == 1
        assert observed.checks[0].rule_id == minimum['rule_id']
        assert observed.checks[0].actual == 0 and not observed.checks[0].satisfied
        assert observed.has_errors and not observed.approval_granted
        legacy = SourceRelations(artifact_bytes(proposal(maturity='approved')))
        assert RelationObligations([legacy], profile_rules=rules).checks == ()
    assert profile_applies(effective.data, applied)
    assert not profile_applies(effective.data, proposal(maturity='approved'))
    program = SrxProgram(rule['program'], rule_id=rule['rule_id'])
    assert evaluate(program, EvaluationContext(roots(applied), rule_id=rule['rule_id'])) is False


def test_applied_review_policy_retains_wildcard_and_exact_severities():
    for maturities in ([], ['applied']):
        resource = profile(relation_review_policy=[{'relation_types': ['references'],
            'maturities': maturities, 'status': 'suspect', 'severity': 'error'}])
        effective = composed(resource)
        assert effective.relation_review_severity('references', 'applied', 'suspect') == 'error'
        assert effective.relation_review_severity('references', 'applied', 'unreviewed') == 'warning'
        assert effective.relation_review_severity('references', 'applied', 'invalid') == 'error'
        assert effective.relation_review_severity('references', 'applied', 'current') is None
    with pytest.raises(ProfileError) as caught:
        profile(relation_review_policy=[{'relation_types': ['references'],
            'maturities': maturities, 'status': 'suspect', 'severity': 'error'}
            for maturities in ([], ['applied'])])
    assert caught.value.reason == 'profile_duplicate_review_policy'


def test_other_artifact_types_and_unknown_maturities_are_still_rejected():
    resource = profile()
    effective = composed(resource)
    for kind in ('goal need capability requirement scenario decision risk assumption component interface '
                 'source verification test evidence release milestone task term baseline issue document '
                 'section content_block view code_ref relation_review configuration').split():
        for check, contract in ((check_profile_fields, resource), (check_composed_fields, effective)):
            with pytest.raises(ProfileError) as caught:
                check(contract, {'artifact_type': kind, 'maturity': 'applied'})
            assert caught.value.reason == 'profile_invalid_maturity'
    for maturity in ('passed', '', None, True):
        with pytest.raises(ProfileError):
            check_profile_fields(resource, {'artifact_type': 'proposal', 'maturity': maturity})
        with pytest.raises(ProfileError):
            profile(required_fields=[scoped(maturities=[maturity], fields=['/rationale'])])
        with pytest.raises(ProfileError):
            effective.relation_review_severity('references', maturity, 'suspect')
        with pytest.raises(ModelError):
            NormalizedQuery(filters={'maturity': [maturity]})


def test_query_reads_applied_without_reclassifying_legacy_originals():
    applied = proposal()
    legacy = proposal(id=ref('PROP', '1'), maturity='approved')
    approved = proposal(id=ref('PROP', '2'), proposal_status='approved', maturity='approved')
    originals = [artifact_bytes(value) for value in (applied, legacy, approved)]
    records = tuple(SourceRelations(raw) for raw in originals)
    selected = select_query(records, NormalizedQuery(filters={'maturity': ['applied']}), project={})
    assert selected.artifact_ids == (applied['id'],)
    selected = select_query(records, NormalizedQuery(filters={'maturity': ['approved']}), project={})
    assert selected.artifact_ids == (legacy['id'], approved['id'])
    assert [record.source_bytes for record in records] == originals


def test_generic_transitions_cannot_enter_or_leave_applied():
    for kind in ('REQ', 'PROP'):
        for source, target, pointer in (('approved', 'applied', '/to'), ('applied', 'retired', '/from')):
            with pytest.raises(ModelError) as caught:
                ChangeOperation({'op': 'transition', 'target': ref(kind), 'from': source,
                                 'to': target, 'metadata': {}})
            assert caught.value.pointer == pointer
