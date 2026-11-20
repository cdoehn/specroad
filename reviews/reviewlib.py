"""Validate review evidence and compute coverage; never attest on a person's behalf."""
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import tempfile
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


def item_binding(module, item):
    """Other items do not invalidate an unchanged item and its complete criteria."""
    return digest(dict(format_version=1, module_id=module['id'], title=module['title'],
        purpose=module['purpose'], source=module['source'], criteria=module['criteria'],
        minimum_reviewers=module['minimum_reviewers'],
        section=next(s for s in module['sections'] if s['id'] == item['section']), item=item))


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


def assess(module, reviews):
    """Pure review aggregation. Accepted means reported review coverage, never release."""
    validate_module(module)
    require(type(reviews) is list and len(reviews) <= MAX_FILES, 'Invalid review inventory')
    for record in reviews:
        validate_review(record)
    items = {item['id']: item for item in module['items']}
    rows = {key: [] for key in items}
    stale = []
    seen = set()
    records = {record['id']: record for record in reviews}
    superseded = set()
    for record in reviews:
        for decision in record['decisions']:
            for old_id in decision.get('supersedes', []):
                require(old_id in records, 'Superseded record is missing')
                old = records[old_id]
                require(old['reviewer']['email'].casefold() == record['reviewer']['email'].casefold(), 'Cannot supersede another reviewer')
                require(old['created_at'] < record['created_at'], 'Supersession must advance time')
                targets = [d for d in old['decisions'] if d['item_id'] == decision['item_id']]
                require(len(targets) == 1 and targets[0]['item_sha256'] == decision['item_sha256'], 'Supersession has a different item binding')
                superseded.add((old_id, decision['item_id']))
    for review in sorted(reviews, key=lambda r: r.get('id', '')):
        validate_review(review)
        require(review['id'] not in seen, 'Duplicate review ID')
        seen.add(review['id'])
        require(review['module_id'] == module['id'], 'Wrong review module')
        for decision in review['decisions']:
            key = decision['item_id']
            if key not in items or decision['item_sha256'] != item_binding(module, items[key]):
                stale.append(dict(review_id=review['id'], item_id=key))
                continue
            require(items[key]['section'] in review['attestations'], 'Missing section attestation')
            require(not items[key]['required_note'] or decision['note'].strip(), 'Missing required evidence note')
            rows[key].append(dict(review_id=review['id'], reviewer=review['reviewer'],
                superseded=(review['id'], key) in superseded, **decision))
    results = []
    for key, item in items.items():
        decisions = rows[key]
        active = [d for d in decisions if not d['superseded']]
        approvals = {d['reviewer']['email'].casefold() for d in active if d['verdict'] == 'accept'}
        conflict = any(d['verdict'] != 'accept' for d in active)
        status = 'changes_requested' if conflict else ('accepted' if len(approvals) >= module['minimum_reviewers'] else 'pending')
        results.append(dict(id=key, section=item['section'], status=status, approvals=len(approvals), reviews=decisions))
    accepted = sum(row['status'] == 'accepted' for row in results)
    return dict(module_id=module['id'], module_sha256=digest(module), total=len(items), accepted=accepted,
        open=len(items)-accepted, review_coverage_complete=accepted == len(items), release_accepted=False,
        items=results, stale=stale)


def safe_directory(path):
    path = Path(os.path.abspath(path))
    for parent in (*reversed(path.parents), path):
        require(stat.S_ISDIR(parent.lstat().st_mode), 'Linked or missing directory')
    return path


def read_file(path):
    safe_directory(path.parent)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= MAX_BYTES, 'Linked, special or oversized input')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        actual = os.fstat(stream.fileno())
        require(stat.S_ISREG(actual.st_mode) and actual.st_nlink == 1, 'Linked or special opened input')
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                (actual.st_dev, actual.st_ino, actual.st_size, actual.st_mtime_ns), 'Input changed while opening')
        raw = stream.read(MAX_BYTES + 1)
        end = os.fstat(stream.fileno())
        require((end.st_size, end.st_mtime_ns, end.st_ctime_ns, end.st_nlink) ==
                (actual.st_size, actual.st_mtime_ns, actual.st_ctime_ns, actual.st_nlink), 'Input changed while reading')
    safe_directory(path.parent)
    require(path.lstat() == end, 'Input changed after reading')
    return decode(raw)


def load_repository(root):
    root = safe_directory(root)
    module_dir = safe_directory(root / 'modules')
    result_dir = safe_directory(root / 'results')
    modules, reviews = {}, {}
    total_bytes = 0
    module_paths = list(module_dir.iterdir())
    require(len(module_paths) <= 100, 'Too many modules')
    for path in sorted(module_paths):
        require(path.suffix == '.json', 'Unexpected module entry')
        module = validate_module(read_file(path))
        require(path.name == module['id'] + '.json' and module['id'] not in modules, 'Module path mismatch')
        modules[module['id']], reviews[module['id']] = module, []
        total_bytes += path.stat().st_size
        require(total_bytes <= MAX_TOTAL_BYTES, 'Review repository too large')
    require(1 <= len(modules) <= 100, 'Invalid module count')
    count = 0
    folders = list(result_dir.iterdir())
    require(len(folders) <= 101, 'Too many result directories')
    for folder in sorted(folders):
        if folder.name == '.gitkeep':
            info = folder.lstat()
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size == 0, 'Invalid placeholder')
            continue
        require(folder.name in modules, 'Unknown result module')
        safe_directory(folder)
        paths = list(folder.iterdir())
        require(count + len(paths) <= MAX_FILES, 'Too many review files')
        for path in sorted(paths):
            count += 1
            require(count <= MAX_FILES and path.suffix == '.json', 'Unexpected or excessive results')
            total_bytes += path.lstat().st_size
            require(total_bytes <= MAX_TOTAL_BYTES, 'Review repository too large')
            review = validate_review(read_file(path))
            require(review['module_id'] == folder.name and path.name == review['id'] + '.json', 'Review path mismatch')
            reviews[folder.name].append(review)
    reports = [assess(module, reviews[key]) for key, module in modules.items()]
    return modules, reports


def markdown_text(value):
    # Numeric entities keep untrusted names, titles and emails inert in Markdown.
    return ''.join(f'&#{ord(c)};' if c in '&<>|`*_[]()!\\#\n\r\t' or 0x202A <= ord(c) <= 0x202E or 0x2066 <= ord(c) <= 0x2069 else c for c in value)


def render_summary(modules, reports):
    lines = ['# Reviews', '', '<!-- Generated by python3 reviews/manage.py summary; edit JSON sources. -->', '',
        'Offene menschliche Abnahmen. [Anleitung und neue Module](GUIDE.md) · [Offline-Formular](index.html).', '',
        'Bewertungen sind persönliche Angaben mit öffentlichem Namen und E-Mail; ihre Identität und Befugnis werden im Beitragsreview geprüft.',
        'Review-Abdeckung ist kein bestandener Adaptertest und keine Releasefreigabe. Mehrere Reviews bleiben sichtbar.', '']
    for report in reports:
        module = modules[report['module_id']]
        lines += ['## ' + markdown_text(module['title']), '',
            f"{report['accepted']}/{report['total']} Prüfpunkte bestätigt; **{report['open']} offen**; {len(report['stale'])} veraltete Einzelbewertungen.", '',
            f"Modul: [JSON](modules/{module['id']}.json). SHA-256: `{report['module_sha256']}`.", '',
            '| Teil | Bestätigt | Offen |', '| --- | ---: | ---: |']
        for section in module['sections']:
            rows = [r for r in report['items'] if r['section'] == section['id']]
            done = sum(r['status'] == 'accepted' for r in rows)
            lines.append(f"| {markdown_text(section['title'])} | {done} | {len(rows)-done} |")
        lines += ['', '| Bewerteter Prüfpunkt | Stand | Reviewer und Belege (mehrfach möglich) |', '| --- | --- | --- |']
        for row in report['items']:
            if not row['reviews']:
                continue
            people = []
            for decision in row['reviews']:
                person = decision['reviewer']
                label = markdown_text(person['name'] + ' <' + person['email'] + '>')
                link = f"results/{module['id']}/{decision['review_id']}.json"
                people.append(f"[{label}]({link}): {decision['verdict']}" + (' (ersetzt)' if decision.get('superseded') else ''))
            lines.append(f"| {row['id']} | {row['status']} | {'; '.join(people)} |")
        if not any(r['reviews'] for r in report['items']):
            lines.append('| — | Noch keine Bewertungen | — |')
        if report['stale']:
            lines += ['', 'Veraltet (nicht mitgezählt): ' + ', '.join(
                f"{r['item_id']} [{r['review_id']}](results/{module['id']}/{r['review_id']}.json)" for r in report['stale'])]
        lines.append('')
    return '\n'.join(lines)


def publish_summary(root, content):
    root = safe_directory(root)
    destination = root / 'README.md'
    if os.path.lexists(destination):
        info = destination.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'Unsafe summary destination')
    fd, temporary = tempfile.mkstemp(prefix='.summary-', dir=root)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content.encode('utf-8'))
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run(root, command):
    modules, reports = load_repository(root)
    if command == 'summary':
        publish_summary(root, render_summary(modules, reports))
    else:
        require(command == 'validate', 'Unknown command')
    return dict(format_version=1, valid=True, modules=[{k: r[k] for k in (
        'module_id', 'module_sha256', 'total', 'accepted', 'open', 'review_coverage_complete', 'release_accepted')} for r in reports])
