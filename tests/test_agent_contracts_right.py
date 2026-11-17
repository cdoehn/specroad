"""Real handler refusals, immutable descriptions and variant-specific requests."""
from copy import deepcopy
import pytest
from specroad.cli.application import execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.registry import CommandRegistry
from specroad.cli.requests import CommandRequest
from specroad.cli.invocation_context import InvocationContextBuilder
from specroad.changes import PublicationAuthority
from specroad.cli.self_description import describe_command
from specroad.cli.capabilities import capabilities
from specroad.model._schema import validate_builtin
from specroad.model.errors import ModelError
from support.read_only import inventory


def test_each_variant_exposes_the_fields_accepted_by_its_actual_binding():
    registry=builtin_registry()
    for command in registry.commands:
        description=describe_command(registry,command.command_id)
        for variant in description.get('variants',[]):
            validate_builtin(variant['example'],variant['request_schema'])
            selected=registry.bind_request(CommandRequest.from_mapping(variant['example'])).command
            assert selected.command_id == variant['command_id']
            assert selected.command_class.value == variant['command_class']
            assert selected.effect_scope.value == variant['effect_scope']
            invalid=deepcopy(variant['example']);invalid['options']['--pretend-human']=True
            with pytest.raises(ModelError): validate_builtin(invalid,variant['request_schema'])


def test_description_mutation_never_creates_permission_or_registers_a_command():
    registry=builtin_registry();before=describe_command(registry,'proposal.review')
    changed=describe_command(registry,'proposal.review')
    changed['authorization'].update(human_decision_required=False,autonomous_approval=True)
    changed['request_schema']['additionalProperties']=True
    assert describe_command(registry,'proposal.review') == before
    empty=CommandRegistry(())
    assert capabilities(empty)['semantic']['commands'] == []
    assert capabilities(empty)['semantic']['supported_versions']['proposal'] == []


@pytest.mark.parametrize('actor',['ai','ci'])
def test_declared_human_only_review_really_refuses_nonhuman_requests(tmp_path,actor):
    from support.proposal_validation import validation_project
    root=tmp_path/'project';_,original=validation_project(root)
    description=describe_command(builtin_registry(),'proposal.review')
    request=description['examples'][0]
    request['arguments']['proposal']=original.data['id']
    request['options'].update({'--project':str(root),'--actor-type':actor,
                              '--request-id':'nonhuman-review','--expected-revision':'1'})
    authority_calls=[]
    def unexpected_authorization(publication):
        authority_calls.append(publication)
        raise AssertionError('A nonhuman review must fail before authorization')
    builder=InvocationContextBuilder(publication_authority=PublicationAuthority(
        'synthetic-agent-review-host','1',unexpected_authorization))
    before=inventory(root)
    response=execute_request(request,context_builder=builder).result
    assert description['authorization']['human_decision_required']
    assert response.exit_code == 7 and inventory(root) == before
    assert response.details['reason'] == 'human_review_required'
    assert not authority_calls


def test_unimplemented_writer_and_unbound_permission_fields_stay_usage_errors(tmp_path):
    before=inventory(tmp_path)
    for request in ({'command_id':'proposal.create'},
                    {'command_id':'proposal.review','authorized':True},
                    {'command_id':'version','options':{'--as-proposal':True}}):
        assert execute_request(request).result.exit_code == 2
    assert inventory(tmp_path) == before
