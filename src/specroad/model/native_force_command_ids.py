"""Shared implemented semantic Force command identities, without execution."""
from .authoring_command_ids import COMMANDS as AUTHORING_COMMANDS
from .plan_command_ids import COMMANDS as PLAN_COMMANDS

PROPOSAL_COMMANDS = ('proposal.review.start', 'proposal.review', 'proposal.apply')
SAVED_COMMANDS = ('merge.apply', 'migrate.apply')
COMMANDS = (*AUTHORING_COMMANDS, *PLAN_COMMANDS, *PROPOSAL_COMMANDS, *SAVED_COMMANDS)
