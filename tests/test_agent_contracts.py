"""Agents bind real structured requests; descriptions never execute or authorize."""
from specroad.cli.commands import builtin_registry
from specroad.cli.registry import CommandRegistry
from specroad.cli.requests import CommandRequest
from specroad.cli.self_description import describe_command
from specroad.cli.capabilities import capabilities
from specroad.cli.result_schemas import validate_result_document
from specroad.model.schema_catalog import SchemaCatalog
from support.read_only import no_write_attempts


def test_all_current_descriptions_supply_valid_requests_and_actual_result_schemas():
    registry=builtin_registry();catalog=SchemaCatalog(registry)
    with no_write_attempts():
        for command in registry.commands:
            description=describe_command(registry,command.command_id)
            validate_result_document('command-description-v1',description)
            result=catalog.get(description['stdout']['result_schema'])
            assert result.schema['$id'] == command.protocol.result_schema
            request=description['examples'][0]
            catalog.validate(description['request_schema']['$id'],request)
            assert registry.bind_request(CommandRequest.from_mapping(request)).command.command_id == command.command_id
            assert not description['authorization']['declaration_is_permission']
            assert not description['authorization']['autonomous_approval']


def test_human_review_and_approved_apply_have_distinct_machine_prerequisites():
    registry=builtin_registry()
    review=describe_command(registry,'proposal.review')['authorization']
    apply=describe_command(registry,'proposal.apply')['authorization']
    start=describe_command(registry,'proposal.review.start')['authorization']
    assert review['human_decision_required'] and review['host_authority_required']
    assert not review['current_human_reviews_required']
    assert apply['current_human_reviews_required'] and apply['host_authority_required']
    assert not apply['human_decision_required']
    assert start['host_authority_required'] and not start['human_decision_required']


def test_proposal_version_requires_an_actual_registered_native_reader():
    registry=builtin_registry()
    assert capabilities(registry)['semantic']['supported_versions']['proposal'] == ['0.2.0']
    removed=CommandRegistry(tuple(c for c in registry.commands if c.command_id != 'proposal.validate'))
    assert capabilities(removed)['semantic']['supported_versions']['proposal'] == []
    assert SchemaCatalog(removed).get('urn:specroad:schema:0.2.0:artifact-record:proposal')
    assert 'python.authoring.proposal' in capabilities(CommandRegistry(()))['semantic']['capability_ids']
    assert 'cli.proposal.create' not in capabilities(registry)['semantic']['capability_ids']
