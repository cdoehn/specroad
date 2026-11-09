"""Passive invocation audit initialization; no persisted status or authority."""
from datetime import datetime, timezone
from .._metadata import __version__


def _now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _initial():
    return dict(format_version='proposal-check-v1', passed=False, observed_status=None,
        eligible_transition=None, binding=None, proposal_sha256=None, context_sha256=None,
        target_model_root_sha256=None, target_sources_sha256=None, checks={},
        audit=dict(proposal_id=None, base=None, tool_version=__version__, started_at=_now(),
            ended_at=None, outcome='failed', diagnostics=[], created_ids=[], changed_ids=[], removed_ids=[]),
        workspace=dict(retained=False, path=None, cleanup='not_created'),
        full_semantic_validation=False, approval_granted=False, write_authorized=False)
