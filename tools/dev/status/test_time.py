#!/usr/bin/env python3
"""Show the currently slowest SpecRoad tests, without running tests or writing data."""
import argparse
from contextlib import closing
from datetime import datetime
import json
import math
from pathlib import Path
import sqlite3
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cli import Target, Terminal, error_output, number, parser_for, terminal


def duration(nanoseconds):
    """Round once to tenths of a second, including the carry into minutes."""
    tenths = (nanoseconds + 50_000_000) // 100_000_000
    minutes, remainder = divmod(tenths, 600)
    seconds, tenth = divmod(remainder, 10)
    return f'{minutes} min {seconds:02d},{tenth} s'


def safe_text(value):
    return ''.join(c if c.isprintable() else ' ' for c in str(value))


def current_tests(repository):
    """Use existing collection evidence; do not import or collect product tests."""
    paths = list((repository / 'build').glob('apply-*/*/gate/catalog.json'))
    path = max(paths, key=lambda p: p.stat().st_mtime_ns, default=None)
    if path is None:
        return None, None
    with path.open('rb') as stream:
        value = json.load(stream)
    pairs = value.get('nodeid_to_test_id')
    if (value.get('catalog_valid') is not True or value.get('collection_exit_code') != 0
            or not isinstance(pairs, dict) or not pairs
            or any(not isinstance(v, str) or not v for v in pairs.values())
            or len(set(pairs.values())) != len(pairs)):
        raise ValueError('Die neueste Apply-Collection ist unvollständig oder ungültig; bitte erneut abfragen.')
    return set(pairs.values()), str(path)


def ranking(database, identities=None, count=20, *, min_seconds=0, match=''):
    """One consistent read transaction, latest started attempt wins even on failure.

    Baseline seeds are eligible only if the test has never had an attempt in
    the shared history. This matches Apply's latest-runtime selection policy.
    """
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True, timeout=3)) as db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        if [tuple(row) for row in db.execute('SELECT id,version FROM metadata')] != [(1, 1)]:
            raise ValueError('Unbekanntes Format der Laufzeitdatenbank')
        attempts = [dict(row) for row in db.execute('''
            WITH latest AS (SELECT MAX(id) AS id FROM attempts GROUP BY test)
            SELECT a.test,a.invalid,a.complete,SUM(p.duration) AS duration_ns,
                   COUNT(DISTINCT p.phase) AS phase_count,
                   MIN(CASE WHEN p.phase IN ('setup','call','teardown')
                            AND p.outcome='passed' AND typeof(p.duration)='integer'
                            AND p.duration>=0 THEN 1 ELSE 0 END) AS phases_valid
            FROM latest l JOIN attempts a ON a.id=l.id
            LEFT JOIN phases p ON p.attempt=a.id GROUP BY a.id
        ''')]
        seeds = [dict(row) for row in db.execute('''
            SELECT test,duration FROM seeds
            WHERE id IN (SELECT MAX(id) FROM seeds GROUP BY test)
        ''')]
    attempted = {row['test'] for row in attempts}
    known = attempted | {row['test'] for row in seeds}
    candidates = []
    for row in attempts:
        if (row['invalid'] == 0 and row['complete'] == 1 and row['phase_count'] == 3
                and row['phases_valid'] == 1 and type(row['duration_ns']) is int):
            candidates.append({'test_name': row['test'], 'duration_ns': row['duration_ns'], 'origin': 'attempt'})
    for row in seeds:
        if row['test'] not in attempted and type(row['duration']) is int and row['duration'] >= 0:
            candidates.append({'test_name': row['test'], 'duration_ns': row['duration'], 'origin': 'baseline'})
    if identities is not None:
        candidates = [row for row in candidates if row['test_name'] in identities]
    else:
        identities = known
    candidates.sort(key=lambda row: (-row['duration_ns'], row['test_name']))
    matching = [row for row in candidates if row['duration_ns'] >= min_seconds * 1e9
                and match.casefold() in row['test_name'].casefold()]
    return {'known_tests': len(identities), 'valid_measurements': len(candidates),
            'matching_measurements': len(matching),
            'without_valid_measurement': len(identities) - len(candidates),
            'tests': [{**row, 'rank': rank, 'duration': duration(row['duration_ns'])}
                      for rank, row in enumerate(matching[:count], 1)]}


def positive_count(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError('Die Anzahl muss mindestens 1 sein.')
    return number


def seconds_value(value):
    try:
        seconds = float(value)
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError
        return seconds
    except ValueError:
        raise argparse.ArgumentTypeError('Mindestdauer muss eine endliche Zahl ab 0 sein.') from None


def collect(repository, count=20, *, apply_directory=None, database=None, min_seconds=0, match=''):
    selected = Target.from_repository(repository, apply_directory=apply_directory, database=database)
    if not selected.repository.is_dir():
        raise ValueError(f'Apply-Verzeichnis fehlt: {selected.repository}')
    ready, warning = selected.runtime_ready()
    warnings = [warning] if warning else []
    identities, collection = current_tests(selected.repository)
    result = {'known_tests': len(identities or []), 'valid_measurements': 0,
              'without_valid_measurement': len(identities or []), 'matching_measurements': 0, 'tests': []}
    if not ready:
        status = 'configuration_pending'
    elif not selected.database.is_file():
        status = 'no_history'
    else:
        result = ranking(selected.database, identities, count, min_seconds=min_seconds, match=match)
        status = 'ok' if result['tests'] else 'no_matches' if result['valid_measurements'] else 'no_measurements'
    return {**result, **selected.metadata(), 'status': status, 'warnings': warnings,
            'observed_at': datetime.now().astimezone().isoformat(timespec='seconds'),
            'collection': collection, 'filters': {'min_seconds': min_seconds, 'match': match, 'count': count}}


def render(report, ui=None, details=False):
    ui = ui or Terminal()
    ui.header('TEST TIME', report.get('target', 'apply'), report.get('repository'))
    if report.get('database_explicit'):
        ui.line('Datenbank: ' + report['database'], 'dim')
    ui.line('Stand: ' + report['observed_at'], 'dim')
    ui.section(f'Langsamste Tests · Top {len(report["tests"])}')
    ui.line('Gemessene Laufzeit = Setup + Call + Teardown', 'dim')
    ui.line(f'Gültig gemessen {number(report["valid_measurements"])}  ·  Ohne gültige aktuelle Messung {number(report["without_valid_measurement"])}', 'cyan')
    ui.line(('Testbestand: letzte Apply-Collection' if report['collection'] else 'Testbestand: eigene Laufzeitdatenbank')
            + f' · {number(report["known_tests"])} Tests', 'dim')
    filters = report.get('filters', {})
    if filters.get('match') or filters.get('min_seconds'):
        ui.line(f'Filter: Name enthält "{filters.get("match", "")}" · ab {filters.get("min_seconds", 0):g} s'
                + f' · {number(report["matching_measurements"])} Treffer', 'magenta')
    longest = max((row['duration_ns'] for row in report['tests']), default=1) or 1
    bar_width = max(8, min(20, ui.width - 40))
    for row in report['tests']:
        ui.line()
        seconds = row['duration_ns'] / 1e9
        style = 'red' if seconds >= 600 else 'yellow' if seconds >= 60 else 'cyan'
        filled = round(bar_width * row['duration_ns'] / longest)
        on, off = ('▰', '▱') if ui.unicode else ('#', '-')
        bar = on * filled + off * (bar_width - filled)
        ui.line(f'{row["rank"]:02d}  {row["duration"]:>14}  {bar}', style)
        ui.line(row['test_name'], indent=6)
        if row['origin'] == 'baseline':
            ui.line('Baseline · importierte Messung, bislang ohne neueren Versuch', 'dim', indent=6)
    if not report['tests']:
        labels = {'configuration_pending': 'Laufzeitdaten noch nicht getrennt eingerichtet.',
                  'no_history': 'Noch keine Laufzeitdatenbank für diese Linie vorhanden.',
                  'no_matches': 'Keine vollständige aktuelle Messung passt zu diesen Filtern.',
                  'no_measurements': 'Noch keine gültigen vollständigen Messungen vorhanden.'}
        ui.line()
        ui.status(labels.get(report.get('status'), 'Keine Messungen vorhanden.'), 'yellow')
    ui.section('Messregeln')
    ui.line('Je Test zählt nur der neueste Versuch. Laufende oder ungültige Versuche sperren ältere Zeiten.', 'dim')
    ui.line('Rot ab 10 Minuten · Gelb ab 1 Minute · Balken relativ zum langsamsten Test.', 'dim')
    ui.warnings(report.get('warnings', []))
    if details:
        ui.section('Datenquellen')
        ui.line('Laufzeiten: ' + report['database'], 'dim')
        if report['collection']:
            ui.line('Collection: ' + report['collection'], 'dim')
    return str(ui)


def main(repository=None, argv=None):
    parser = parser_for('TEST TIME', 'Die aktuell langsamsten Tests aus der gewählten Laufzeitdatenbank anzeigen.', argv,
        'python3 tools/test_time.py\npython3 tools/test_time.py -n 10 --match merge --min-seconds 600\npython3 tools/test_time.py --apply-dir ../specroad-apply2\npython3 tools/test_time.py --database ../exchange/archiv.sqlite3 --json\nwatch -c -n 30 python3 tools/test_time.py -n 6 --color always')
    parser.add_argument('-n', '--count', type=positive_count, default=20, help='Anzahl der Tests (Standard: 20)')
    parser.add_argument('--details', action='store_true', help='zusätzlich die Datenquellen anzeigen')
    parser.add_argument('--match', default='', metavar='TEXT', help='Testnamen filtern (Teiltext, Groß-/Kleinschreibung egal)')
    parser.add_argument('--min-seconds', type=seconds_value, default=0, metavar='SEKUNDEN',
                        help='nur gemessene Laufzeiten ab dieser Dauer anzeigen')
    args = parser.parse_args(argv)
    try:
        report = collect(repository or Path(__file__).resolve().parents[3], args.count,
                         apply_directory=args.apply_dir, database=args.database,
                         min_seconds=args.min_seconds, match=args.match)
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else render(report, terminal(args), args.details))
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError, sqlite3.Error) as error:
        print(error_output(args, 'TEST TIME', error))
        return 2


if __name__ == '__main__':
    sys.exit(main())
