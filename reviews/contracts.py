"""Portable review contracts; no third-party or SpecRoad dependency."""
from datetime import datetime
from hashlib import sha256
import json
import re
import uuid


MAX_BYTES = 2 * 1024 * 1024

MAX_FILES = 10000

MAX_TOTAL_BYTES = 64 * 1024 * 1024

ID = r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}'

MODULE_ID = r'[a-z][a-z0-9-]{0,63}'

HASH = r'[0-9a-f]{64}'


class ReviewError(ValueError):
    """Invalid or unsafe review input; no result may be published."""


def require(condition, message):
    if not condition:
        raise ReviewError(message)


def keys(value, names):
    require(type(value) is dict and set(value) == set(names.split()), 'Unexpected object fields')


def text(value, limit=8000, *, empty=False):
    require(type(value) is str and len(value) <= limit and (empty or value.strip()), 'Invalid text')
    require(not any(ord(c) < 32 and c not in '\n\t' or 0xD800 <= ord(c) <= 0xDFFF for c in value), 'Invalid text codepoint')
    return value


def token(value, pattern=ID):
    require(type(value) is str and re.fullmatch(pattern, value) is not None, 'Invalid identifier')
    return value


def strings(value, limit=100, *, allow_empty=False):
    require(type(value) is list and len(value) <= limit and (allow_empty or value), 'Invalid text list')
    for part in value:
        text(part)
    require(len(value) == len(set(value)), 'Duplicate text')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return sha256(canonical(value)).hexdigest()


def decode(raw):
    require(type(raw) is bytes and len(raw) <= MAX_BYTES, 'Oversized input')
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    def invalid_constant(_):
        raise ReviewError('Non-finite JSON number')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ReviewError('Invalid JSON: ' + str(exc)) from exc


def validate_module(module):
    keys(module, 'format_version id title purpose source minimum_reviewers criteria sections items')
    require(type(module['format_version']) is int and module['format_version'] == 1, 'Unsupported module version')
    token(module['id'], MODULE_ID)
    text(module['title'], 160)
    text(module['purpose'])
    keys(module['source'], 'kind reference note')
    for value in module['source'].values():
        text(value)
    require(type(module['minimum_reviewers']) is int and 1 <= module['minimum_reviewers'] <= 100, 'Invalid reviewer minimum')
    strings(module['criteria'])
    require(type(module['sections']) is list and 1 <= len(module['sections']) <= 100, 'Invalid sections')
    sections = {}
    for section in module['sections']:
        keys(section, 'id title attestation')
        token(section['id'])
        text(section['title'], 160)
        text(section['attestation'])
        require(section['id'] not in sections, 'Duplicate section')
        sections[section['id']] = section
    require(type(module['items']) is list and 1 <= len(module['items']) <= 5000, 'Invalid item count')
    seen = set()
    for item in module['items']:
        keys(item, 'id section title text criteria required_note metadata')
        token(item['id'])
        token(item['section'])
        require(item['id'] not in seen and item['section'] in sections, 'Duplicate item or unknown section')
        seen.add(item['id'])
        text(item['title'], 160)
        text(item['text'])
        strings(item['criteria'], allow_empty=True)
        require(type(item['required_note']) is bool, 'Invalid note policy')
        require(type(item['metadata']) is dict and len(item['metadata']) <= 30, 'Invalid metadata')
        for key, value in item['metadata'].items():
            token(key)
            text(value, 2000)
    require({i['section'] for i in module['items']} == set(sections), 'Empty section')
    require(len(canonical(module)) <= MAX_BYTES, 'Oversized module')
    return module


def validate_review(review):
    keys(review, 'format_version id module_id module_sha256 reviewer created_at publication_consent personal_review attestations decisions')
    require(type(review['format_version']) is int and review['format_version'] == 1, 'Unsupported review version')
    try:
        require(str(uuid.UUID(review['id'])) == review['id'], 'Noncanonical review ID')
    except (ValueError, TypeError, AttributeError) as exc:
        raise ReviewError('Invalid review ID') from exc
    token(review['module_id'], MODULE_ID)
    token(review['module_sha256'], HASH)
    keys(review['reviewer'], 'name email')
    text(review['reviewer']['name'], 160)
    email = review['reviewer']['email']
    text(email, 254)
    require(re.fullmatch(r'[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+', email) is not None, 'Invalid email')
    try:
        stamp = datetime.strptime(review['created_at'], '%Y-%m-%dT%H:%M:%SZ')
        require(stamp.strftime('%Y-%m-%dT%H:%M:%SZ') == review['created_at'], 'Noncanonical date')
    except (ValueError, TypeError) as exc:
        raise ReviewError('Invalid UTC timestamp') from exc
    require(review['publication_consent'] is True and review['personal_review'] is True, 'Missing personal confirmation or publication consent')
    strings(review['attestations'])
    for section in review['attestations']:
        token(section)
    require(type(review['decisions']) is list and 1 <= len(review['decisions']) <= 5000, 'Empty or oversized review')
    seen = set()
    for decision in review['decisions']:
        require(type(decision) is dict, 'Invalid decision')
        keys(decision, 'item_id item_sha256 verdict note proposed_text' + (' supersedes' if 'supersedes' in decision else ''))
        token(decision['item_id'])
        token(decision['item_sha256'], HASH)
        require(decision['item_id'] not in seen, 'Duplicate decision')
        seen.add(decision['item_id'])
        require(decision['verdict'] in ('accept', 'correct', 'reject'), 'Invalid verdict')
        text(decision['note'], empty=decision['verdict'] == 'accept')
        text(decision['proposed_text'], empty=True)
        require(decision['verdict'] == 'correct' or not decision['proposed_text'], 'Unexpected replacement text')
        supersedes = decision.get('supersedes', [])
        strings(supersedes, allow_empty=True)
        for previous in supersedes:
            try:
                require(str(uuid.UUID(previous)) == previous and previous != review['id'], 'Invalid supersession ID')
            except (ValueError, TypeError, AttributeError) as exc:
                raise ReviewError('Invalid supersession ID') from exc
    require(len(canonical(review)) <= MAX_BYTES, 'Oversized review')
    return review
