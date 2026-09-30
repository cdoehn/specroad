"""Point-in-time Hetzner selection, with an explicit hosted alternative.

The manual workflow probes from a small hosted selector. An optional
SPECROAD_RUNNER_READ_TOKEN needs repository Administration:read. With no
usable permission, an unavailable API or an offline/busy runner, the explicit
ubuntu-24.04 alternative is chosen; no success is inferred from that choice.
The API observation is not a reservation or migration of already queued jobs.
"""
from datetime import datetime, timezone
from .contract import CIObservationError, REPOSITORY
from .transport import GhClient, records

NAME = 'Hetzner-specroad'
SELF_HOSTED = ('self-hosted', 'Linux', 'X64', 'specroad', 'hetzner')
HOSTED = ('ubuntu-24.04',)


def runner_labels(choice):
    if choice == 'hetzner':
        return list(SELF_HOSTED)
    if choice == 'github-hosted':
        return list(HOSTED)
    raise ValueError('Unknown runner choice')


def choose_runner(runners):
    """Only one matching, online AND idle runner qualifies; never use Blade."""
    matches = [r for r in runners if type(r) is dict and r.get('name') == NAME]
    if len(matches) != 1:
        return 'github-hosted', 'missing_or_ambiguous_hetzner', None
    candidate = matches[0]
    labels = candidate.get('labels')
    if (type(labels) is not list or any(type(v) is not dict or type(v.get('name')) is not str for v in labels)
            or type(candidate.get('id')) is not int or candidate['id'] < 1):
        return 'github-hosted', 'invalid_runner_record', None
    if not {v.casefold() for v in SELF_HOSTED} <= {v['name'].casefold() for v in labels}:
        return 'github-hosted', 'required_labels_missing', candidate['id']
    if candidate.get('status') != 'online':
        return 'github-hosted', 'hetzner_offline', candidate['id']
    if candidate.get('busy') is not False:
        return 'github-hosted', 'hetzner_not_idle', candidate['id']
    return 'hetzner', 'hetzner_online_idle', candidate['id']


def probe_runner(*, client=None):
    client = GhClient() if client is None else client
    try:
        choice, reason, identity = choose_runner(records(
            client, 'repos/' + REPOSITORY + '/actions/runners', 'runners'))
    except (CIObservationError, OSError):
        choice, reason, identity = 'github-hosted', 'runner_query_unavailable', None
    return {'format_version': 1, 'repository': REPOSITORY, 'runner_name': NAME,
            'runner_id': identity, 'choice': choice, 'runs_on': runner_labels(choice),
            'reason': reason, 'checked_at': datetime.now(timezone.utc).isoformat(),
            'reservation': False}


def commit_runner(message):
    """Missing legacy trailer means hosted; malformed/duplicate input fails."""
    values = []
    for line in message.splitlines():
        key, sep, value = line.partition(':')
        if sep and key == 'SpecRoad-CI-Runner':
            values.append(value.strip())
    if not values:
        return 'github-hosted'
    if len(values) != 1:
        raise ValueError('Ambiguous runner trailer')
    runner_labels(values[0])
    return values[0]


def terminal_ci_status(status):
    """Observation failures/missing full gates are not a successful CI run."""
    return {'success': 'SUCCESS', 'failed': 'FAILED', 'cancelled': 'CANCELLED'}.get(status, 'UNAVAILABLE')
