"""Terminal presentation only. Import curses lazily so JSON works without a TTY."""
from dataclasses import dataclass, field
from datetime import datetime
import os
import time

from .cli import Terminal, cells, safe_text
from .monitor_data import filtered

VIEWS = ('status', 'running', 'runtimes', 'failures')
TITLES = ('Status', 'Offene Tests', 'Laufzeiten', 'Fehler / Quellen')
TIME_VIEWS = ('total', 'phases', 'both')
SORTS = ('total', 'setup', 'call', 'teardown', 'elapsed')
LABELS = {'total': 'Gesamt', 'setup': 'Setup', 'call': 'Call', 'teardown': 'Teardown',
          'elapsed': 'Seit Start', 'name': 'Name'}
STATES = {'free': 'FREI', 'busy': 'BELEGT', 'unknown': 'UNKLAR',
          'missing': 'FEHLT', 'unregistered': 'NICHT REGISTRIERT'}


def clock(seconds):
    if seconds is None:
        return '—'
    if seconds < 60:
        return f'{seconds:.2f}s'
    value = int(seconds)
    h, rem = divmod(value, 3600)
    m, s = divmod(rem, 60)
    return f'{h}h{m:02d}m{s:02d}s' if h else f'{m}m{s:02d}s'


def source(target, name):
    return target[name]['data'] or {}


def report(target):
    return source(target, 'status').get('report', {})


def freshness(target):
    stale = [name for name in ('status', 'history') if target[name]['stale']]
    if stale:
        return 'VERALTET: ' + ', '.join(stale)
    return 'lädt …' if any(target[s]['refreshing'] for s in ('status', 'history')) else 'gelesen'


def overview(target):
    view = report(target)
    counts = view.get('tests') or {}
    state = STATES.get(view.get('availability', {}).get('state'), 'LÄDT')
    if target['status']['stale']:
        state = 'UNKLAR (alter Stand)'
    run = counts.get('run') or {}
    progress = f'{counts.get("ended", 0)}/{counts.get("total", "?")}' if counts else '—'
    return (f'{target["repository"].rsplit("/", 1)[-1]:<21} {state:<23} '
            f'Bundle {view.get("bundle") or "—":>4}  {view.get("phase", view.get("status", "")):<12} '
            f'{progress:>12}  {run.get("workers", "—")} W  {freshness(target)}')


def detail_lines(target):
    view = report(target)
    tests = view.get('tests') or {}
    run = source(target, 'status').get('run') or tests.get('run') or {}
    lines = [target['repository'],
             f'Belegung: {STATES.get(view.get("availability", {}).get("state"), "unbekannt")} '
             f'· letzter Lauf: {view.get("status", "wird gelesen")} · {freshness(target)}']
    if run:
        start = datetime.fromisoformat(run['started']).timestamp()
        end = datetime.fromisoformat(run['finished']).timestamp() if run.get('finished') else view.get('observed_at', time.time())
        lines.append(f'Testlauf {clock(max(0, end - start))} · {run["workers"]} Worker · '
                     f'{tests.get("ended", "?")}/{tests.get("total", "?")} beendet · '
                     f'{tests.get("passed", 0)} bestanden · {tests.get("failed", 0)} Fehler · '
                     f'{tests.get("open", "?")} offen')
    lines.append('Commits: ' + (' | '.join(f'{s["commit_id"]}: {s["status"]}' for s in view.get('stages', [])) or '—'))
    return lines


def rows_for(target, tab, state):
    if tab == 'runtimes':
        rows = source(target, 'history').get('tests', [])
    else:
        rows = source(target, 'status').get('tests', [])
        if tab == 'running':
            rows = [r for r in rows if not r['completed']]
        elif tab == 'failures':
            rows = [r for r in rows if r['status'] in ('failed', 'skipped', 'invalid')]
    return filtered(rows, match=state.match, minimum=state.minimum, sort=state.sort,
                    descending=state.descending, limit=state.limit)


def times(row, mode):
    parts = []
    if mode != 'phases':
        parts.append(f'{clock(row.get("total_seconds")):>12}')
    if mode != 'total':
        parts.extend(f'{clock(row.get(p + "_seconds")):>12}' for p in ('setup', 'call', 'teardown'))
    parts.append(f'{clock(row.get("elapsed_seconds")):>12}')
    return ' '.join(parts)


def time_header(mode):
    labels = ([] if mode == 'phases' else ['Gesamt']) + ([] if mode == 'total' else ['Setup', 'Call', 'Teardown'])
    return ' '.join(f'{label:>12}' for label in labels + ['Seit Start'])


def notes(target):
    view = report(target)
    result = list(view.get('warnings', [])) + list(source(target, 'history').get('warnings', []))
    if view.get('error'):
        result.append(view['error'])
    for name in ('status', 'history'):
        if target[name]['error']:
            result.append(name + ': ' + target[name]['error'])
        data = source(target, name)
        if data.get('status') in ('configuration_pending', 'no_history'):
            result.append(name + ': ' + data['status'])
    result.append('Belegung ist eine Momentaufnahme, keine Reservierung. Offen bedeutet nicht sicher laufend.')
    return list(dict.fromkeys(result))


@dataclass
class ViewState:
    tab: str = 'status'
    time_view: str = 'both'
    match: str = ''
    minimum: float = 0
    sort: str = 'total'
    descending: bool = True
    limit: int = 200
    target: int = 0
    focus: str = 'targets'
    selections: dict = field(default_factory=dict)
    offsets: dict = field(default_factory=dict)

    @classmethod
    def from_args(cls, args):
        return cls(tab=args.view, time_view=args.time_view, match=args.match,
                   minimum=args.min_seconds, sort=args.sort, descending=not args.ascending, limit=args.limit)

    def position(self, path, rows):
        key = (path, self.tab)
        identity = self.selections.get(key)
        return next((i for i, r in enumerate(rows) if r['test_name'] == identity), 0)


def render_once(snapshot, args):
    ui = Terminal(args.color, args.plain)
    ui.header('TEST MONITOR', f'{len(snapshot["repositories"])} Apply-Ziele')
    ui.line('Stand: ' + snapshot['observed_at'], 'dim')
    for target in snapshot['repositories']:
        ui.line(overview(target), 'yellow' if target['status']['stale'] else 'cyan')
    state = ViewState.from_args(args)
    for target in snapshot['repositories']:
        ui.section(target['repository'].rsplit('/', 1)[-1] + ' · ' + TITLES[VIEWS.index(state.tab)])
        for line in detail_lines(target):
            ui.line(line)
        rows, count = rows_for(target, state.tab, state)
        ui.line(f'{count} Treffer · Sortierung {LABELS[state.sort]} · Sekunden bzw. h/m/s', 'dim')
        ui.line(time_header(state.time_view), 'title')
        for row in rows:
            ui.line(times(row, state.time_view) + '  ' + row['status'], 'red' if row['status'] == 'failed' else 'cyan')
            ui.line(row['nodeid'] or row['test_name'], indent=4)
        if not rows:
            ui.line('Keine passenden Messungen vorhanden.', 'dim')
        ui.warnings(notes(target))
        ui.line('Datenbank: ' + str(view_database(target)), 'dim')
        if report(target).get('report_directory'):
            ui.line('Berichte: ' + report(target)['report_directory'], 'dim')
    return str(ui)


def view_database(target):
    return report(target).get('database') or source(target, 'history').get('database') or 'unbekannt'


def run_tui(paths, args):
    import curses
    from .monitor import Refresh

    refresh = Refresh(paths, database=args.database, interval=args.interval,
                      history_interval=args.history_interval, timeout=args.query_timeout)
    state = ViewState.from_args(args)

    def session(screen):
        screen.keypad(True)
        screen.timeout(200)
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        colored = not args.plain and args.color != 'never' and (args.color == 'always' or 'NO_COLOR' not in os.environ)
        if colored and curses.has_colors():
            curses.start_color()
            try:
                curses.use_default_colors()
                background = -1
            except curses.error:
                background = curses.COLOR_BLACK
            for i, color in enumerate((curses.COLOR_CYAN, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_RED), 1):
                curses.init_pair(i, color, background)
        else:
            colored = False
        search = None
        help_open = False
        refresh.request()

        def put(y, x, text, color=0, selected=False):
            height, width = screen.getmaxyx()
            if y < 0 or y >= height or x >= width - 1:
                return
            text = safe_text(text)
            available, cropped = width - x - 1, ''
            for char in text:
                size = cells(char)
                if size > available:
                    break
                cropped += char
                available -= size
            attr = curses.color_pair(color) if colored and color else 0
            if selected:
                attr |= curses.A_REVERSE
            try:
                screen.addstr(y, x, cropped, attr)
            except (curses.error, UnicodeError):
                pass  # resize or a terminal unable to encode one glyph

        while True:
            refresh.harvest()
            refresh.request()
            snapshots = refresh.snapshot()
            target = snapshots[state.target]
            rows, matches = rows_for(target, state.tab, state)
            position = state.position(target['repository'], rows)
            key = (target['repository'], state.tab)
            if rows:
                state.selections[key] = rows[position]['test_name']
            screen.erase()
            height, width = screen.getmaxyx()
            if height < 20 or width < 80:
                put(0, 0, 'test-monitor: Terminal mindestens 80×20; q beendet.', 3)
                list_start, capacity = height, 0
            else:
                put(0, 1, 'SPECROAD  /  TEST MONITOR', 1)
                put(1, 1, f'{len(paths)} Apply-Ziele · Status {args.interval:g}s / Historie {args.history_interval:g}s'
                    + f' · Fokus: {"Apply-Übersicht" if state.focus == "targets" else "Testliste"}', 1)
                visible_targets = min(5, len(snapshots))
                first = max(0, min(state.target - visible_targets + 1, len(snapshots) - visible_targets))
                for index in range(first, first + visible_targets):
                    item = snapshots[index]
                    availability = report(item).get('availability', {}).get('state')
                    color = 3 if item['status']['stale'] else 2 if availability == 'free' else 3 if availability in ('unknown', 'busy') else 1
                    put(3 + index - first, 1, ('› ' if index == state.target else '  ') + overview(item), color,
                        selected=index == state.target and state.focus == 'targets')
                line = 4 + visible_targets
                put(line, 1, '   '.join(('[' if view == state.tab else '') + f'{i + 1} {title}'
                    + (']' if view == state.tab else '') for i, (view, title) in enumerate(zip(VIEWS, TITLES))), 1)
                for extra, text in enumerate(detail_lines(target)[:4], 1):
                    put(line + extra, 1, text, 3 if 'VERALTET' in text else 0)
                line += 5
                put(line, 1, f'Suche: {state.match or "—"} · {matches} Treffer / {len(rows)} angezeigt · '
                    f'{LABELS[state.sort]} {"↓" if state.descending else "↑"} · Zeiten: {state.time_view}', 1)
                put(line + 1, 1, time_header(state.time_view) + '  Worker / Status / Test', 1)
                list_start = line + 2
                capacity = max(0, height - list_start - 4)
                offset = state.offsets.get(key, 0)
                offset = max(0, min(offset, position, max(0, len(rows) - capacity)))
                if capacity and position >= offset + capacity:
                    offset = position - capacity + 1
                state.offsets[key] = offset
                for i, row in enumerate(rows[offset:offset + capacity]):
                    text = times(row, state.time_view) + f'  {row.get("worker") or "—":<4} {row["status"]:<10} ' + row['test_name']
                    color = 4 if row['status'] == 'failed' else 3 if (row.get('total_seconds') or row.get('elapsed_seconds') or 0) >= 600 else 0
                    put(list_start + i, 1, text, color, selected=offset + i == position and state.focus == 'tests')
                if not rows:
                    messages = notes(target)
                    put(list_start, 1, messages[0] if messages else 'Noch keine passenden Messungen.', 3)
                if rows:
                    selected_row = rows[position]
                    put(height - 4, 1, selected_row['nodeid'] or selected_row['test_name'], 1)
                messages = notes(target)
                extra = ('DB: ' + str(view_database(target)) + ' · Berichte: ' + report(target).get('report_directory', '—')) if state.tab == 'failures' else (messages[0] if messages else '')
                put(height - 3, 1, extra, 3)
                put(height - 2, 1, 'Tab Fokus · ↑↓ PgUp/PgDn · 1–4 Ansicht · / Suche · t Zeiten · [ ] Sortierung · d/n · r · ? · q', 1)
                put(height - 1, 1, '— = unbekannt. Seit Start = verstrichen, keine Messung. Keine Reservierung / Dienststeuerung.', 3)
            if help_open:
                screen.erase()
                help_lines = [
                    'TEST MONITOR · Bedienung (? oder Esc schließt)', '',
                    'Tab: Fokus zwischen Apply-Übersicht und Testliste wechseln.',
                    'Pfeile / j k: Ziel bzw. Test wählen. PgUp/PgDn, Home/End: Liste bewegen.',
                    '1 Status (alle gestarteten Tests), 2 offene Tests, 3 Laufzeithistorie, 4 Fehler/Quellen.',
                    '/: Testname/Node-ID durchsuchen; Enter übernimmt; Esc verwirft; leer löscht.',
                    't: Gesamt / Setup+Call+Teardown / beide. Seit Start bleibt separat sichtbar.',
                    '[ und ]: Sortierfeld Gesamt/Setup/Call/Teardown/Seit Start wählen.',
                    'd: Dauer absteigend bzw. Richtung umkehren. n: Name bzw. Richtung umkehren.',
                    'r: Quellen neu lesen (bereits laufende Abfragen werden nicht verdoppelt).',
                    'q / Strg-C: Nur den Monitor beenden; Apply und Tests laufen weiter.', '',
                    'Gesamt wird nur mit allen drei Messphasen berechnet. Baselines haben nur Gesamt.',
                    'Letzter Versuch zählt; fehlgeschlagene/offene Versuche verdrängen alte Erfolge.',
                    'Offen heißt ohne Abschluss. Prozesssicht kann fehlen; keine Laufgarantie.',
                    'VERALTET: letzte lesbare Daten; insbesondere keine aktuelle Freimeldung.',
                    'Belegung und letzter Bundle-Erfolg sind getrennt. Keine Restzeitprognose.',
                    'Einmal JSON: python3 tools/test-monitor --all --once --json',
                ]
                for i, text in enumerate(help_lines):
                    put(i + 1, 1, text, 1 if i == 0 else 0)
            if search is not None:
                put(height - 1, 0, '/ ' + search + '  [Enter übernehmen · Esc zurück]', 1, True)
            screen.refresh()
            try:
                pressed = screen.get_wch()
            except curses.error:
                continue
            if search is not None:
                if pressed in ('\n', '\r', curses.KEY_ENTER):
                    state.match, search = search, None
                elif pressed == '\x1b':
                    search = None
                elif pressed in ('\b', '\x7f', curses.KEY_BACKSPACE):
                    search = search[:-1]
                elif isinstance(pressed, str) and pressed.isprintable() and len(search) < 512:
                    search += pressed
                continue
            if pressed == 'q':
                break
            if pressed == '?' or help_open and pressed == '\x1b':
                help_open = not help_open
                continue
            if help_open:
                continue
            if pressed == '\t':
                state.focus = 'tests' if state.focus == 'targets' else 'targets'
            elif pressed in ('1', '2', '3', '4'):
                state.tab = VIEWS[int(pressed) - 1]
            elif pressed == '/':
                search = state.match
            elif pressed == 't':
                state.time_view = TIME_VIEWS[(TIME_VIEWS.index(state.time_view) + 1) % len(TIME_VIEWS)]
            elif pressed == 'r':
                refresh.request(force=True)
            elif pressed == 'n':
                state.descending = not state.descending if state.sort == 'name' else False
                state.sort = 'name'
            elif pressed == 'd':
                state.descending = not state.descending if state.sort != 'name' else True
                state.sort = state.sort if state.sort != 'name' else 'total'
            elif pressed in ('[', ']'):
                index = SORTS.index(state.sort) if state.sort in SORTS else 0
                state.sort = SORTS[(index + (1 if pressed == ']' else -1)) % len(SORTS)]
            elif pressed in (curses.KEY_UP, curses.KEY_DOWN, 'j', 'k', curses.KEY_NPAGE, curses.KEY_PPAGE, curses.KEY_HOME, curses.KEY_END):
                delta = -1 if pressed in (curses.KEY_UP, 'k') else 1
                if state.focus == 'targets':
                    state.target = max(0, min(len(paths) - 1, state.target + delta))
                elif rows:
                    if pressed in (curses.KEY_NPAGE, curses.KEY_PPAGE):
                        delta = max(1, capacity) * (1 if pressed == curses.KEY_NPAGE else -1)
                    position = 0 if pressed == curses.KEY_HOME else len(rows) - 1 if pressed == curses.KEY_END else max(0, min(len(rows) - 1, position + delta))
                    state.selections[key] = rows[position]['test_name']
        return 0

    try:
        return curses.wrapper(session)
    finally:
        refresh.close()
