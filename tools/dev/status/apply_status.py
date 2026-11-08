#!/usr/bin/env python3
"""Read-only SpecRoad Apply status. Python standard library; no model or services.

Run python3 tools/apply_status.py, --details, or --json inside the selected repository.
No product code is imported and no tests are started. Existing native locks
are probed briefly without creating, changing or reserving any file.
"""
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cli import Target, Terminal, error_output, parser_for, terminal


from availability import repository_availability


AVAILABILITY = {
    'free': ('FREI · native Apply-Sperre ist frei', 'green'),
    'busy': ('BELEGT · Apply-Sperre oder Prozess aktiv', 'yellow'),
    'unknown': ('UNKLAR · nicht sicher als frei bestätigt', 'yellow'),
    'unregistered': ('NICHT EINGERICHTET · native Registrierung fehlt', 'yellow'),
    'missing': ('NICHT VORHANDEN · Apply-Verzeichnis fehlt', 'red'),
}


def read_json(path, limit=16_000_000):
    if path.stat().st_size > limit:
        raise ValueError(f'Datei zu groß: {path.name}')
    with path.open('rb') as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f'Kein JSON-Objekt: {path.name}')
    return value


def stamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Zeitangabe ohne Zeitzone')
    return parsed.timestamp()


def local_time(value):
    return datetime.fromtimestamp(value).astimezone().strftime('%d.%m.%Y %H:%M:%S')


def duration(seconds):
    seconds = max(0, int(seconds))
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return (f'{hours}h ' if hours else '') + f'{minutes:02d}m {seconds:02d}s'


def number(value):
    return f'{value:,}'.replace(',', '.') if value is not None else 'unbekannt'


def safe_text(value):
    # Do not let filenames, test parameters or exception text control a terminal.
    return ''.join(c if c.isprintable() else ' ' for c in str(value))


def process_view(repository, proc_root=Path('/proc')):
    """A missing PID in a container is not proof that the host job stopped."""
    visibility, processes = 'full', []
    try:
        if (proc_root / '1/comm').read_text().strip() not in ('systemd', 'init'):
            visibility = 'limited'
        paths = list(proc_root.glob('[0-9]*'))
        for path in paths:
            try:
                if path.stat().st_uid != os.getuid():
                    continue
                args = path.joinpath('cmdline').read_bytes()[:65536].decode(errors='replace').split('\0')
                cwd = Path(os.readlink(path / 'cwd'))
                state = (path / 'stat').read_text().rsplit(')', 1)[1].split()[0]
                if state in ('Z', 'X') or not args or int(path.name) == os.getpid():
                    continue
                executable = Path(args[0]).name
                python = re.fullmatch(r'python(?:[0-9]+(?:\.[0-9]+)*)?', executable) is not None

                def script_argument(name):
                    return python and '-c' not in args and any(
                        arg in ('tools/' + name, str(repository / 'tools' / name)) for arg in args[1:])

                kind = None
                if cwd == repository:
                    if script_argument('run_apply_tests.py'):
                        kind = 'test_runner'
                    elif script_argument('verify_apply_commit.py'):
                        kind = 'gate_verification'
                    elif 'apply' in args and (executable == 'patchharbor'
                            or python and len(args) > 1 and Path(args[1]).name == 'patchharbor'
                            or python and args[1:3] == ['-m', 'patchharbor']):
                        kind = 'apply'
                    elif python and args[1:] == ['-I', '-B', '-', '']:
                        kind = 'entrypoint'
                if kind:
                    outdir = None
                    if '--outdir' in args:
                        outdir = str((cwd / args[args.index('--outdir') + 1]).resolve())
                    processes.append({'pid': int(path.name), 'kind': kind, 'outdir': outdir})
            except PermissionError:
                visibility = 'limited'
            except (OSError, ValueError, IndexError):
                continue  # A process may exit during this read-only snapshot.
    except OSError:
        visibility = 'unavailable'
    return {'visibility': visibility, 'processes': processes}


def latest_bundle(repository, processes):
    build = repository / 'build'
    candidates = [p for p in build.glob('apply-*')
                  if re.fullmatch(r'apply-[0-9]+-[A-Za-z0-9_]+', p.name) and p.is_dir()]
    # Prefer the exact live runner over directory timestamps when /proc is visible.
    for process in processes:
        if process['outdir']:
            for candidate in candidates:
                if candidate in Path(process['outdir']).parents:
                    return candidate
    return max(candidates, key=lambda p: p.stat().st_mtime_ns, default=None)


def progress_at(bundle):
    paths = sorted(bundle.glob('progress-*.json'),
                   key=lambda p: int(p.stem.split('-')[-1]) if p.stem.split('-')[-1].isdigit() else -1)
    if not paths:
        return None, None
    # Do not fall back to an old success if the newest file is incomplete.
    path = paths[-1]
    value = read_json(path, 1_000_000)
    if value.get('kind') != 'specroad-apply-progress-v1' or value.get('format_version') != 1:
        raise ValueError('Unbekanntes Apply-Fortschrittsformat')
    if not isinstance(value.get('committed'), list) or not isinstance(value.get('remaining_commit_ids'), list):
        raise ValueError('Unvollständiger Apply-Fortschritt')
    return value, path


def runtime_counts(database, gate, stage_started, stage_ended=None):
    """Bind by code identity AND stage time AND selected native node IDs."""
    catalog_path, nodes_path = gate / 'catalog.json', gate / 'nodeids.txt'
    if not catalog_path.is_file() or not nodes_path.is_file():
        return None
    catalog = read_json(catalog_path)
    source = catalog.get('source_sha256')
    if not isinstance(source, str) or not re.fullmatch('[0-9a-f]{64}', source):
        raise ValueError('Quellbindung der Collection fehlt')
    nodes = nodes_path.read_text().splitlines()
    if not nodes or len(nodes) != len(set(nodes)):
        raise ValueError('Testauswahl ist leer oder mehrdeutig')
    selected = set(nodes)
    lower_bound = datetime.fromtimestamp(stage_started - 1, timezone.utc).isoformat()
    upper_bound = datetime.fromtimestamp(stage_ended + 1, timezone.utc).isoformat() if stage_ended else '9999'
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)) as db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        runs = db.execute('SELECT * FROM runs WHERE source=? AND started>=? AND started<=? ORDER BY id',
                          (source, lower_bound, upper_bound)).fetchall()
        # A second same-source run is ambiguous: never silently show another job.
        if len(runs) > 1:
            raise ValueError('Mehrere Testläufe passen zum Zustand; keine sichere Zuordnung')
        if not runs:
            return {'total': len(nodes), 'run': None}
        run = dict(runs[0])
        rows = [dict(row) for row in db.execute('''
            SELECT a.id,a.node,a.worker,a.started,a.invalid,a.complete,p.phase,p.outcome,p.recorded
            FROM attempts a LEFT JOIN phases p ON p.attempt=a.id
            WHERE a.run=? ORDER BY a.id''', (run['id'],))]
    attempts = {}
    for row in rows:
        node = row['node']
        if node not in selected:
            raise ValueError('Messlauf enthält Tests außerhalb dieser Apply-Auswahl')
        item = attempts.setdefault(node, {**row, 'phases': {}})
        if item['id'] != row['id']:
            raise ValueError('Doppelte Testversuche im Lauf')
        if row['phase']:
            item['phases'][row['phase']] = (row['outcome'], row['recorded'])
    passed = failed = skipped = invalid = ended = 0
    pending, failures, activity = [], [], [stamp(run['started'])]
    for node, item in attempts.items():
        phases = item['phases']
        outcomes = {p[0] for p in phases.values()}
        activity.append(stamp(item['started']))
        activity.extend(stamp(p[1]) for p in phases.values())
        terminal = 'teardown' in phases
        ended += terminal
        has_error = bool(outcomes & {'failed', 'error', 'unexpected_success'})
        if has_error:
            failed += 1
            failures.append(node)
        elif terminal and item['complete'] and not item['invalid'] and outcomes == {'passed'}:
            passed += 1
        elif terminal and outcomes & {'skipped', 'expected_failure'}:
            skipped += 1
        elif terminal:
            invalid += 1
        if not terminal:
            pending.append({'nodeid': node, 'worker': item['worker'], 'started': item['started'],
                            'phase': 'teardown' if 'call' in phases else 'call' if 'setup' in phases else 'setup'})
    pending.sort(key=lambda item: item['started'])
    return {'total': len(nodes), 'run': run, 'started': len(attempts), 'ended': ended,
            'passed': passed, 'failed': failed, 'skipped': skipped, 'invalid': invalid,
            'unfinished_started': len(pending), 'not_started': len(nodes) - len(attempts),
            'open': len(nodes) - ended, 'last_activity': max(activity),
            'pending': pending, 'failures': failures}


def result_receipt(repository, head):
    """Existing watcher receipt, no watcher/API calls and no ZIP traversal."""
    state_home = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state')))
    path = state_home / 'patchharbor/exchange/state.json'
    if not path.is_file():
        return None
    repo_id = (repository / '.patchharbor/id').read_text().strip()
    state = read_json(path)
    matches = [item for item in state.get('entries', [])
               if item.get('kind') == 'patch_package' and item.get('completed_commit') == head
               and item.get('apply_status') == 'succeeded'
               and item.get('manifest', {}).get('repo_id') == repo_id
               and item.get('result_sha256')]
    if len(matches) == 1:
        return {'result_sha256': matches[0]['result_sha256'], 'patch': Path(matches[0]['path']).name}
    return None


def collect(repository, *, apply_directory=None, database=None):
    now = time.time()
    selected = Target.from_repository(repository, apply_directory=apply_directory, database=database)
    repository = selected.repository
    view = {'observed_at': now, 'status': 'unknown', 'root': str(selected.root), 'warnings': [],
            'bundle': None, 'tests': None, 'stages': [], 'result': None, **selected.metadata()}
    if not repository.is_dir():
        raise ValueError(f'Apply-Verzeichnis fehlt: {repository}')
    runtime_ready, warning = selected.runtime_ready()
    if warning:
        view['warnings'].append(warning)
    if not (repository / '.patchharbor/id').is_file():
        view['warnings'].append('Dieses Apply-Ziel ist noch nicht bei PatchHarbor registriert.')
    proc = process_view(repository)
    view['processes'] = proc
    view['availability'] = repository_availability(repository, proc['processes'])
    bundle = latest_bundle(repository, proc['processes'])
    if bundle is None:
        view['status'] = 'running' if proc['processes'] else 'no_history'
        return view
    view['bundle'] = bundle.name.split('-')[1]
    view['report_directory'] = str(bundle)
    progress, path = progress_at(bundle)
    if progress is None:
        if view['availability']['state'] == 'free':
            view['availability'].update(state='unknown', reason='missing_progress')
        view['status'] = 'preparing' if proc['processes'] else 'unknown'
        view['warnings'].append('Für dieses Bundle liegt noch kein Fortschrittsbericht vor.')
        return view
    view.update(phase=progress['phase'], progress_updated_at=path.stat().st_mtime,
                active_commit=progress['active_commit_id'], error=progress.get('error'))
    if view['availability']['state'] == 'free' and progress['phase'] not in ('completed', 'failed'):
        view['availability'].update(state='unknown', reason='unfinished_progress')
    completed = progress['committed']
    view['stages'] = [{'commit_id': item['commit_id'], 'status': 'committed', 'commit': item['commit'],
                       'passed_tests': item['gate']['tests']} for item in completed]
    view['stages'] += [{'commit_id': name,
                       'status': progress['phase'] if name == progress['active_commit_id'] else 'pending'}
                      for name in progress['remaining_commit_ids']]
    current = progress['active_commit_id'] or (completed[-1]['commit_id'] if completed else None)
    if current and re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*', current):
        stage = bundle / current
        testing, gates_ended = [], []
        for checkpoint in bundle.glob('progress-*.json'):
            value = read_json(checkpoint, 1_000_000)
            if value.get('active_commit_id') == current and value.get('phase') == 'testing':
                testing.append(checkpoint.stat().st_mtime)
            if value.get('active_commit_id') == current and value.get('phase') in ('committing', 'failed'):
                gates_ended.append(checkpoint.stat().st_mtime)
        if testing and runtime_ready:
            try:
                view['tests'] = runtime_counts(selected.database,
                                               stage / 'gate', min(testing), min(gates_ended, default=None))
            except (OSError, ValueError, sqlite3.Error) as error:
                view['warnings'].append('Testzahlen nicht sicher lesbar: ' + str(error))
        view['test_commit'] = current
    if progress['phase'] == 'completed':
        view['status'] = 'completed'
        try:
            view['result'] = result_receipt(repository, progress['actual_head'])
        except (OSError, ValueError, KeyError, TypeError) as error:
            view['warnings'].append('Result-Nachweis nicht lesbar: ' + str(error))
        if proc['processes']:
            view['status'] = 'running'
            view['warnings'].append('Apply-Prozess aktiv; der letzte erfasste Bundle-Stand ist bereits abgeschlossen.')
    elif progress['phase'] == 'failed':
        view['status'] = 'failed'
    elif proc['processes']:
        view['status'] = 'running'
    elif proc['visibility'] == 'full':
        view['status'] = 'stopped_incomplete'
    else:
        tests = view['tests']
        if tests and tests.get('run') and not tests['run']['finished'] and now - tests['last_activity'] < 120:
            view['status'] = 'recent_activity'
        else:
            view['status'] = 'unknown'
        view['warnings'].append('Host-Prozesse sind hier nicht vollständig sichtbar; laufende Tests sind nicht sicher bestätigbar.')
    # Re-read the checkpoint name once to detect a stage change during observation.
    latest = max(bundle.glob('progress-*.json'), key=lambda p: p.stat().st_mtime_ns, default=path)
    if latest != path:
        view['warnings'].append('Apply wechselte während der Abfrage die Phase; bitte erneut aufrufen.')
    return view


PHASES = {'started': 'Vorbereitung', 'materializing': 'Dateien werden ausgebracht',
          'testing': 'Testprüfung', 'committing': 'Commit wird erstellt',
          'committed': 'Commit erstellt', 'completed': 'abgeschlossen',
          'failed': 'fehlgeschlagen', 'pending': 'noch ausstehend'}


def render(view, details=False, ui=None):
    ui = ui or Terminal()
    states = {'running': ('Läuft · Prozess erkannt', 'cyan'),
              'preparing': ('Vorbereitung läuft', 'cyan'),
              'completed': ('Bundle erfolgreich abgeschlossen', 'green'),
              'failed': ('Bundle fehlgeschlagen', 'red'),
              'stopped_incomplete': ('Gestoppt · Bundle unvollständig', 'yellow'),
              'recent_activity': ('Frische Testaktivität · Prozessstatus nicht sichtbar', 'cyan'),
              'unknown': ('Laufstatus nicht sicher feststellbar', 'yellow'),
              'no_history': ('Noch kein Apply-Lauf vorhanden', 'dim')}
    ui.header('APPLY STATUS', view.get('target', 'apply'), view.get('repository'))
    if view.get('database_explicit'):
        ui.line('Datenbank: ' + view['database'], 'dim')
    ui.line('Stand: ' + local_time(view['observed_at']), 'dim')
    ui.line()
    ui.status(*AVAILABILITY[view['availability']['state']])
    label, style = states[view['status']]
    ui.status(label, style)
    if view['bundle']:
        ui.line(f'Bundle {view["bundle"]}  ·  {PHASES.get(view.get("phase"), "Vorbereitung")}', 'bold')
    if view['stages']:
        ui.section('Commit-Fortschritt')
        for stage in view['stages']:
            detail = PHASES.get(stage['status'], stage['status'])
            style = 'green' if stage['status'] == 'committed' else 'red' if stage['status'] == 'failed' else 'dim' if stage['status'] == 'pending' else 'cyan'
            symbol = ('✓' if ui.unicode else '+') if stage['status'] == 'committed' else ('›' if ui.unicode else '>')
            if stage['status'] == 'committed':
                detail += f' · {stage["commit"][:10]} · {number(stage["passed_tests"])} Tests bestanden'
            ui.line(f'{symbol} {stage["commit_id"]}  {detail}', style)
        done = sum(s['status'] == 'committed' for s in view['stages'])
        ui.progress(done, len(view['stages']), 'green' if done == len(view['stages']) else 'cyan')
        ui.line(f'{number(sum(s.get("passed_tests", 0) for s in view["stages"]))} bestandene Testausführungen vor diesen Commits', 'dim')
    tests = view['tests']
    if tests:
        run = tests.get('run')
        ui.section(f'Tests · {view["test_commit"]}')
        if not run:
            ui.line(f'Auswahl: {number(tests["total"])} Tests · noch kein zugehöriger Messlauf.', 'yellow')
        else:
            elapsed = (stamp(run['finished']) if run['finished'] else view['observed_at']) - stamp(run['started'])
            ui.line(f'Dauer {duration(elapsed)}  ·  {run["workers"]} Worker  ·  Start {local_time(stamp(run["started"]))}', 'bold')
            ui.progress(tests['ended'], tests['total'], 'red' if tests['failed'] else 'green' if tests['ended'] == tests['total'] else 'cyan')
            ui.line(f'Bestanden {number(tests["passed"])}  ·  Fehler {number(tests["failed"])}  ·  Übersprungen/XFail {number(tests["skipped"])}', 'red' if tests['failed'] else 'green')
            if tests['invalid']:
                ui.line(f'Ohne gültigen Erfolgsnachweis: {number(tests["invalid"])}', 'yellow')
            if run['finished']:
                ui.line(f'Testlauf beendet: {local_time(stamp(run["finished"]))} · Exit-Code {run["exit_code"]}', 'green' if run['exit_code'] == 0 else 'red')
                if tests['unfinished_started']:
                    ui.line(f'Ohne Abschluss: {number(tests["unfinished_started"])} gestartete Tests', 'yellow')
            else:
                confirmed = view['status'] == 'running' and any(p['kind'] == 'test_runner' for p in view['processes']['processes'])
                label = 'Laufen gerade' if confirmed else 'Gestartet, ohne Abschluss'
                ui.line(f'{label}: {number(tests["unfinished_started"])}', 'cyan')
            ui.line(f'Noch nicht gestartet {number(tests["not_started"])}  ·  Insgesamt offen {number(tests["open"])}')
            ui.line(f'Letzter Fortschritt vor {duration(view["observed_at"] - tests["last_activity"])}', 'dim')
            if tests['pending']:
                ui.section('Gestartet, noch ohne Abschluss' + ('' if details else ' · längste 3'))
                for item in tests['pending'][:None if details else 3]:
                    elapsed = (stamp(run['finished']) if run['finished'] else view['observed_at']) - stamp(item['started'])
                    ui.line(f'{item["worker"]}  ·  {duration(elapsed)} seit Start  ·  Phase {item["phase"]}', 'yellow' if elapsed >= 600 else 'cyan')
                    ui.line(item['nodeid'], indent=4)
            if tests['failures']:
                ui.section('Fehlgeschlagene Tests')
                for node in tests['failures'][:None if details else 3]:
                    ui.line(node, 'red')
    elif view.get('phase') == 'testing':
        ui.section('Tests')
        ui.line('Collection/Vorprüfung oder Messdaten noch nicht verfügbar.', 'yellow')
    if view.get('phase') == 'completed':
        ui.section('Result')
        ui.line('Veröffentlichung vom Watcher bestätigt.' if view['result'] else 'Veröffentlichung noch nicht bestätigt.',
                'green' if view['result'] else 'yellow')
    if view.get('error'):
        ui.section('Apply-Fehler')
        ui.line(view['error'], 'red')
    ui.warnings(view['warnings'])
    if details:
        ui.section('Datenquellen')
        if view.get('report_directory'):
            ui.line('Berichte: ' + view['report_directory'], 'dim')
        ui.line('Laufzeiten: ' + view.get('database', 'unbekannt'), 'dim')
        ui.line('Belegungsgrund: ' + view['availability']['reason'], 'dim')
        if view['availability'].get('detail'):
            ui.line(view['availability']['detail'], 'yellow')
    ui.line('Belegung ist eine Momentaufnahme, keine Reservierung.', 'dim')
    return str(ui)


def collect_overview(repository):
    workspace = Path(repository).resolve().parent
    reports = []
    for name in ('specroad-apply', 'specroad-apply2'):
        target = workspace / name
        try:
            report = collect(repository, apply_directory=target)
        except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
            availability = (repository_availability(target, process_view(target)['processes'])
                if target.is_dir() else {'state': 'missing', 'reason': 'missing_directory', 'reserved': False})
            report = {'target': name.removeprefix('specroad-'), 'repository': str(target),
                      'status': 'unavailable', 'availability': availability, 'error': str(error)}
        reports.append(report)
    return {'observed_at': time.time(), 'repositories': reports, 'reserved': False}


def render_overview(report, ui, details=False):
    ui.header('APPLY-BELEGUNG', 'Übersicht')
    ui.line('Stand: ' + local_time(report['observed_at']), 'dim')
    for view in report['repositories']:
        ui.section(view['target'].upper())
        ui.status(*AVAILABILITY[view['availability']['state']])
        ui.line(view['repository'], 'dim')
        if view.get('bundle'):
            ui.line(f'Letzter Bericht: Bundle {view["bundle"]} · {PHASES.get(view.get("phase"), view["status"])}')
        if view.get('tests') and view['tests'].get('run'):
            tests = view['tests']
            ui.line(f'Tests: {number(tests["ended"])} / {number(tests["total"])} beendet · {number(tests["open"])} offen')
        if view.get('error'):
            ui.line(view['error'], 'red')
        if details:
            ui.line('Belegungsgrund: ' + view['availability']['reason'], 'dim')
            if view['availability'].get('detail'):
                ui.line(view['availability']['detail'], 'yellow')
            ui.warnings(view.get('warnings', []))
    ui.line()
    ui.line('Momentaufnahme; keine Reservierung und kein Start von Apply oder Tests.', 'dim')
    return str(ui)


def main(repository=None, argv=None):
    parser = parser_for('APPLY STATUS', 'Apply, Commit-Fortschritt und offene Tests einmalig anzeigen.', argv,
        'python3 tools/apply_status.py\npython3 tools/apply_status.py --all\npython3 tools/apply_status.py --details\npython3 tools/apply_status.py --apply-dir ../specroad-apply2\nwatch -c -n 10 python3 tools/apply_status.py --all --color always')
    parser.add_argument('--details', action='store_true', help='alle offenen/fehlgeschlagenen Tests und Datenquellen')
    parser.add_argument('--all', action='store_true', help='Belegung beider Apply-Kopien im Workspace anzeigen')
    args = parser.parse_args(argv)
    if args.all and (args.apply_dir is not None or args.database is not None):
        parser.error('--all verwendet jede eigene Quelle; Pfadoptionen bitte bei Einzelabfragen verwenden.')
    repository = repository or Path(__file__).resolve().parents[3]
    try:
        view = collect_overview(repository) if args.all else collect(repository, apply_directory=args.apply_dir, database=args.database)
        formatted = render_overview(view, terminal(args), args.details) if args.all else render(view, args.details, terminal(args))
        print(json.dumps(view, ensure_ascii=False, indent=2) if args.json else formatted)
        return 0
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
        print(error_output(args, 'APPLY STATUS', error))
        return 2


if __name__ == '__main__':
    sys.exit(main())
