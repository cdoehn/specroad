"""Finite, byte-granular Restore capture tasks over explicit native boundaries.

Enumeration reads declarations, not payloads or a guessed current model. Only
full qualification may turn the retained original bytes into a Restore plan.
"""
from base64 import b64encode, b64decode
from hashlib import sha256
import os
import stat
import zipfile

from ..archive.objects import ObjectReference
from ..archive.verification import _configuration
from ..model.canonical import canonical_json_sha256
from ..model.configuration import ProjectConfiguration
from ..model.errors import ModelError
from ..model.record_schemas import validate_record_fields
from ..recovery._codec import safe_path, namespace, file_row
from ..recovery._coverage import inventory_roots
from ..recovery._current_evidence import BASELINES, _intact
from ..recovery._inventory import boundary, check_aliases, read_source
from ..recovery.values import require, RestoreError
from ..security.resource_access import opened_resource, directory_entries
from ..storage.json_syntax import parse_json_object

ADAPTER = 'native-restore-planning-capture-v1'
BLOCK = 65536


def _signature(info):
    return sha256(':'.join(str(v) for v in (info.st_dev, info.st_ino, info.st_size,
                                           info.st_mtime_ns, info.st_ctime_ns)).encode('ascii')).hexdigest()


def enumerate_entries(bound, roots):
    pending = [(p, True) for p in reversed(roots)]
    entries = []
    while pending:
        path, optional = pending.pop()
        safe_path(path)
        check_aliases(bound, path)
        with opened_resource(bound, path, directory=None, missing_ok=optional) as (fd, info):
            if fd is None:
                row = {'path': path, 'kind': 'missing'}
            elif stat.S_ISDIR(info.st_mode):
                row = {'path': path, 'kind': 'directory'}
                children = directory_entries(bound, path)
                pending.extend((path + '/' + name, False) for name, _ in reversed(children))
            else:
                require(info.st_nlink == 1, 'restore_linked_file', path=path, exit_code=7)
                row = {'path': path, 'kind': 'file', 'size': info.st_size, 'signature': _signature(info)}
        entries.append(row)
    namespace([row['path'] for row in entries])
    return sorted(entries, key=lambda row: row['path'].encode())


def _baseline_declarations(origin, path, seen=None):
    seen = set() if seen is None else seen
    require(path not in seen, 'restore_baseline_cycle')
    seen.add(path)
    raw = read_source(origin, path)
    record = parse_json_object(raw)
    validate_record_fields(record, expected_type='baseline')
    rows = {}
    configuration = None
    for row in record['manifest']:
        ref = ObjectReference(row['sha256'], row['size'])
        require(row['object_path'] == ref.path, 'restore_baseline_object_path_mismatch')
        rows[ref.path] = ref.size
        if row['role'] == 'semantic_configuration':
            content = read_source(origin, ref.path)
            require(len(content) == ref.size and sha256(content).hexdigest() == ref.sha256,
                    'restore_baseline_object_bytes_mismatch', path=ref.path)
            configuration = parse_json_object(content)
        if row['role'] == 'artifact' and row.get('artifact_type') == 'baseline':
            nested, _ = _baseline_declarations(origin, ref.path, seen)
            for name, size in nested.items():
                require(name not in rows or rows[name] == size, 'restore_baseline_object_conflict')
                rows[name] = size
    seen.remove(path)
    require(configuration is not None, 'restore_semantic_configuration_missing')
    return rows, configuration


def _source_declarations(options):
    origin = boundary(options['--source-root'])
    path = options['--from']
    safe_path(path)
    check_aliases(origin, path)
    if options['--source-kind'] == 'baseline':
        dependencies, semantic = _baseline_declarations(origin, path)
        configuration = ProjectConfiguration({**semantic,
            'default_locale': options['--default-locale'], 'generated_path': options['--generated-path']})
        paths = [path, *sorted(dependencies)]
    else:
        # Reading only this closed metadata entry does not qualify the archive.
        # Its complete original ZIP is captured in blocks and verified later by
        # BundleContainer/verify_bundle, including every path, member and hash.
        with opened_resource(origin, path) as (fd, info):
            require(info.st_nlink == 1, 'restore_linked_file', path=path, exit_code=7)
            try:
                with os.fdopen(os.dup(fd), 'rb') as stream, zipfile.ZipFile(stream) as archive:
                    selected = [entry for entry in archive.infolist() if entry.filename == 'specroad.json']
                    require(len(selected) == 1 and selected[0].compress_type == zipfile.ZIP_STORED,
                            'restore_source_configuration_missing')
                    configuration = ProjectConfiguration(parse_json_object(archive.read(selected[0])))
            except (zipfile.BadZipFile, KeyError, RuntimeError) as error:
                raise RestoreError('restore_source_declaration_invalid') from error
        paths = [path]
    rows = enumerate_entries(origin, paths)
    require(all(row['kind'] == 'file' for row in rows), 'restore_source_file_required')
    return configuration, rows


def _current_declaration(project):
    try:
        raw = read_source(project, 'specroad.json')
    except FileNotFoundError:
        raw = None
    configuration = _intact(raw)
    if configuration is not None:
        return configuration
    # Coverage hints use only retained Baseline headers and semantic config
    # objects. Full recursive archive/identity qualification remains mandatory
    # after capture; no hint becomes an authenticated model or approval.
    configurations = []
    for row in enumerate_entries(project, [BASELINES]):
        if row['kind'] != 'file':
            continue
        try:
            value = parse_json_object(read_source(project, row['path']))
            validate_record_fields(value, expected_type='baseline')
        except ModelError:
            continue
        for item in value['manifest']:
            if item['role'] != 'semantic_configuration':
                continue
            ref = ObjectReference(item['sha256'], item['size'])
            require(ref.path == item['object_path'], 'restore_baseline_object_path_mismatch')
            raw = read_source(project, ref.path)
            require(len(raw) == ref.size and sha256(raw).hexdigest() == ref.sha256,
                    'restore_baseline_object_bytes_mismatch', path=ref.path)
            configurations.append(_configuration(parse_json_object(raw)))
    require(bool(configurations), 'restore_current_configuration_evidence_required')
    first = configurations[0]
    require(all((c.project_id, c.id_prefix, sorted(c.managed_paths)) ==
                (first.project_id, first.id_prefix, sorted(first.managed_paths)) for c in configurations),
            'restore_current_coverage_evidence_conflict')
    return first


def declarations(options):
    source, source_rows = _source_declarations(options)
    project = boundary(options['--project'])
    current = _current_declaration(project)
    roots = inventory_roots(source, current)
    project_rows = enumerate_entries(project, roots)
    return units_for(roots, source_rows, project_rows)


def units_for(roots, source_rows, project_rows):
    units = []
    for phase, rows in (('source_capture', source_rows), ('inventory_capture', project_rows)):
        for row in rows:
            size = row.get('size', 0)
            offsets = range(0, size, BLOCK) if size else (0,)
            for offset in offsets:
                length = min(BLOCK, size - offset)
                units.append({'key': phase + ':' + row['path'] + ':' + str(offset), 'phase': phase,
                    'range': {'adapter': ADAPTER, 'entry': row, 'offset': offset, 'length': length}})
    units.extend({'key': phase, 'phase': phase, 'range': {'adapter': ADAPTER, 'roots': roots}}
                 for phase in ('qualify_plan', 'deliver_plan'))
    return units


def checked_units(tasks, options):
    declarations = [{key: unit[key] for key in ('key', 'phase', 'range')} for unit in tasks]
    require(len(declarations) >= 3, 'restore_capture_tasks_invalid')
    final = declarations[-2:]
    require([unit['phase'] for unit in final] == ['qualify_plan', 'deliver_plan'],
            'restore_capture_tasks_invalid')
    require(all(set(unit['range']) == {'adapter', 'roots'} and unit['range']['adapter'] == ADAPTER
                for unit in final), 'restore_capture_tasks_invalid')
    roots = final[0]['range']['roots']
    require(roots == final[1]['range']['roots'] and type(roots) is list,
            'restore_capture_roots_invalid')
    for path in roots:
        safe_path(path)
    source, project = {}, {}
    for unit in declarations[:-2]:
        r = unit['range']
        require(unit['phase'] in ('source_capture', 'inventory_capture')
                and set(r) == {'adapter', 'entry', 'offset', 'length'} and r['adapter'] == ADAPTER,
                'restore_capture_tasks_invalid')
        entry = r['entry']
        require(type(entry) is dict and entry.get('kind') in ('file', 'directory', 'missing'),
                'restore_capture_tasks_invalid')
        fields = {'path', 'kind', 'size', 'signature'} if entry['kind'] == 'file' else {'path', 'kind'}
        require(set(entry) == fields, 'restore_capture_tasks_invalid')
        safe_path(entry['path'])
        if entry['kind'] == 'file':
            require(type(entry['size']) is int and entry['size'] >= 0
                    and type(entry['signature']) is str and len(entry['signature']) == 64
                    and all(c in '0123456789abcdef' for c in entry['signature']), 'restore_capture_tasks_invalid')
        table = source if unit['phase'] == 'source_capture' else project
        require(entry['path'] not in table or table[entry['path']] == entry, 'restore_capture_tasks_invalid')
        table[entry['path']] = entry
    require(options['--from'] in source and all(row['kind'] == 'file' for row in source.values()),
            'restore_capture_source_invalid')
    require(options['--source-kind'] == 'baseline' or set(source) == {options['--from']},
            'restore_capture_source_invalid')
    namespace(source); namespace(project)
    ordered = lambda table: [table[key] for key in sorted(table, key=lambda p: p.encode())]
    require(declarations == units_for(roots, ordered(source), ordered(project)), 'restore_capture_tasks_invalid')
    return roots


def capture(options, task):
    r = task['range']; entry = r['entry']; path = entry['path']
    root = '--source-root' if task['phase'] == 'source_capture' else '--project'
    bound = boundary(options[root])
    check_aliases(bound, path)
    with opened_resource(bound, path, directory=None, missing_ok=entry['kind'] == 'missing') as (fd, info):
        if entry['kind'] == 'missing':
            require(fd is None, 'restore_inventory_changed', path=path, exit_code=6)
            raw = b''
        elif entry['kind'] == 'directory':
            require(stat.S_ISDIR(info.st_mode), 'restore_inventory_changed', path=path, exit_code=6)
            raw = b''
        else:
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                    and _signature(info) == entry['signature'],
                    'restore_inventory_changed', path=path, exit_code=6)
            os.lseek(fd, r['offset'], os.SEEK_SET)
            parts, remaining = [], r['length']
            while remaining:
                chunk = os.read(fd, remaining)
                require(bool(chunk), 'restore_inventory_changed', path=path, exit_code=6)
                parts.append(chunk); remaining -= len(chunk)
            raw = b''.join(parts)
            after = os.fstat(fd)
            require(after.st_nlink == 1 and _signature(after) == entry['signature'],
                    'restore_inventory_changed', path=path, exit_code=6)
    return {'size': len(raw), 'sha256': sha256(raw).hexdigest(), 'data_base64': b64encode(raw).decode('ascii')}


def chunk_bytes(task, record):
    require(type(record) is dict and set(record) == {'size', 'sha256', 'data_base64'},
            'restore_capture_chunk_invalid')
    raw = b64decode(record['data_base64'], validate=True)
    require(len(raw) == task['range']['length'] == record['size']
            and sha256(raw).hexdigest() == record['sha256']
            and b64encode(raw).decode('ascii') == record['data_base64'], 'restore_capture_chunk_invalid')
    return raw


def assembled(tasks, evidence, roots):
    files = {'source_capture': {}, 'inventory_capture': {}}
    entries = {}
    for task, record in zip(tasks, evidence):
        if task['phase'] not in files:
            break
        entry = task['range']['entry']; path = entry['path']
        if task['phase'] == 'inventory_capture':
            entries[path] = {'path': path, 'kind': entry['kind']}
        if entry['kind'] == 'file':
            files[task['phase']].setdefault(path, []).append(chunk_bytes(task, record['chunk']))
    joined = {phase: {path: b''.join(parts) for path, parts in table.items()} for phase, table in files.items()}
    for path, raw in joined['inventory_capture'].items():
        entries[path] = {**file_row(path, raw), 'kind': 'file'}
    inventory = {'roots': roots, 'entries': [entries[key] for key in sorted(entries, key=lambda p: p.encode())]}
    inventory['sha256'] = canonical_json_sha256(inventory)
    return joined['source_capture'], joined['inventory_capture'], inventory
