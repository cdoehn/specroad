"""Installed project opt-in and the additive, typed optional-clarification ABI."""
import re

MIXED = 'patch_ready_with_clarification'
IMPLEMENTATIONS = ('patch_ready', MIXED)
CAPABILITY_PATH = 'verification/development_contract.json'
CAPABILITY = {'format_version': 1, 'decision_rule': 'SPECROAD-DECISION-1',
    'decision_contract_version': 4, 'bundle_plan_format_version': 2,
    'mixed_status': MIXED, 'clarification_limit': 3, 'max_clarification_stages': 1,
    'clarification_position': 'prefix', 'implementation_required': True}


def capability(value):
    if (type(value) is not dict or set(value) != set(CAPABILITY)
            or any(type(value[k]) is not type(v) or value[k] != v for k, v in CAPABILITY.items())):
        raise ValueError('Unsupported installed development contract')
    return value


def supports_v4(source):
    value = source.get('development_contract')
    if value is None:
        return False
    capability(value)
    return True


def validate_roles(data):
    """Same closed role/scope ABI as SpecRoad Apply plan v2; no execution."""
    roles = [s['role'] for s in data['stages']]
    if any(type(role) is not str or role not in ('clarification', 'implementation', 'correction') for role in roles):
        raise ValueError('Unknown stage role')
    if data['handoff_kind'] == 'patch_ready':
        if 'clarification' in roles:
            raise ValueError('Normal handoff hides clarification')
    elif data['handoff_kind'] == MIXED:
        if roles[0] != 'clarification' or roles.count('clarification') != 1 or 'implementation' not in roles[1:]:
            raise ValueError('Mixed handoff requires one optional prefix and implementation')
        first = data['stages'][0]
        required = {'docs/specification/SpecRoad_Spezifikation.md',
                    'docs/implementation/SpecRoad_Implementierungsplan.md'}
        paths = set(first['after'])
        if not required <= paths or any(not (name in required or name == 'verification/catalog.json'
                or re.fullmatch(r'verification/requirements/SR-TC-[0-9]{4}\.json', name)) for name in paths):
            raise ValueError('Clarification scope is not the normative document/catalog scope')
        if any(first['before'].get(name) == first['after'][name] for name in required):
            raise ValueError('Clarification requires actual specification and plan changes')
        if not any(s['role'] == 'implementation' and any(not name.startswith(('docs/', 'verification/'))
                and s['before'].get(name) != digest for name, digest in s['after'].items()) for s in data['stages'][1:]):
            raise ValueError('An alibi implementation cannot renew authority')
    else:
        raise ValueError('Unknown handoff classification')


def remaining_roles(plan, progress, data):
    """Only an authenticated failed source and its exact open prefix qualify."""
    rest = plan['stages'][len(progress['committed']):]
    if ([s['commit_id'] for s in data['stages']] != [s['commit_id'] for s in rest]
            or [s['role'] for s in data['stages']] != [s['role'] for s in rest]):
        raise ValueError('Correction must retain all unfinished commit IDs and roles')
    for old, new in zip(rest, data['stages']):
        if old['role'] == 'clarification' and old['after'] != new['after']:
            raise ValueError('Pending clarification is not new decision authority')
    return rest
