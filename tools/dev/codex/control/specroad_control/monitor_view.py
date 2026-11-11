"""Curses presentation, with no lifecycle commands or file writers."""
from datetime import datetime
import json
import unicodedata


def safe(value):
    return ''.join(c if c == ' ' or not unicodedata.category(c).startswith('C') else '?' for c in str(value))


def overview(row):
    state = row.get('state') or {}
    auto = state.get('automation') or {}
    freshness = 'VERALTET' if row['stale'] else 'LIVE'
    if row.get('refreshing'):
        freshness += ' / liest'
    return (f"{row['instance']:<16} {freshness:<18} {state.get('phase', '?'):<12} "
            f"Soll {state.get('desired', '?'):<8} {auto.get('stage', '?')}")


def fields(value, prefix=''):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from fields(item, prefix + str(key) + '.')
    else:
        text = json.dumps(value, ensure_ascii=False) if isinstance(value, (list, bool)) else str(value)
        yield prefix.rstrip('.') + ': ' + text


def details(row, tab):
    state = row.get('state') or {}
    auto = state.get('automation') or {}
    if tab == 0:
        value = {'lifecycle': {k: state.get(k) for k in ('phase', 'desired', 'active_job', 'pid', 'run_id',
                 'started_at', 'updated_at', 'development_enabled', 'driver', 'start_delay')},
                 'automation': auto, 'disk_space': state.get('disk_space')}
    elif tab == 1:
        value = {key: row.get(key) for key in ('configured_bindings', 'paths', 'installed_release', 'systemd')}
        value['runtime_bindings'] = state.get('bindings')
    elif tab == 2:
        value = {key: auto.get(key) for key in ('validation', 'job', 'source_sha256', 'patch_sha256',
                 'request_contract', 'retry_attempt', 'retry_at', 'retry_mode', 'overload_check_at',
                 'retry_blocked_reason', 'apply_wait_reason')}
        value['history'] = row.get('history')
        value['handover'] = row.get('handover')
    else:
        value = {'source': row.get('source'), 'observed_at': row.get('observed_at'),
                 'stale': row['stale'], 'errors': row.get('errors'),
                 'runtime_error': state.get('runtime_error'), 'stop_reason': state.get('stop_reason'),
                 'automation_error': auto.get('error'), 'codex_error': auto.get('codex_error')}
    return list(fields(value))


def render_once(report):
    lines = ['CONTROL MONITOR']
    for row in report['instances']:
        lines.append(overview(row))
        lines.extend('  ' + line for line in details(row, 0))
        lines.extend('  ' + line for line in details(row, 3))
    lines.extend(str(error) for error in report.get('discovery_errors', []))
    return '\n'.join(safe(line) for line in lines)


def run_tui(paths, args, errors):
    import curses
    from .monitor_refresh import Refresh
    refresh = Refresh(paths, interval=args.interval, timeout=args.query_timeout)

    def display(screen):
        selected = tab = offset = 0
        help_open = False
        screen.timeout(150)
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        colored = curses.has_colors()
        if colored:
            curses.start_color()
            try:
                curses.use_default_colors()
                for number, foreground in ((1, curses.COLOR_CYAN), (2, curses.COLOR_GREEN), (3, curses.COLOR_YELLOW)):
                    curses.init_pair(number, foreground, -1)
            except curses.error:
                colored = False

        def line(y, text, attr=0):
            height, width = screen.getmaxyx()
            if 0 <= y < height and width > 1:
                try:
                    screen.addnstr(y, 0, safe(text), width - 1, attr)
                except curses.error:
                    pass

        while True:
            refresh.poll()
            rows = refresh.snapshot()['instances']
            selected = min(selected, max(0, len(rows)-1))
            screen.erase()
            height, width = screen.getmaxyx()
            line(0, 'CONTROL MONITOR  |  ' + datetime.now().strftime('%H:%M:%S'), curses.A_BOLD | (curses.color_pair(1) if colored else 0))
            if height < 9 or width < 40:
                line(2, 'Terminal vergrößern. q beendet.')
            else:
                visible = max(1, min(len(rows), height//3))
                start = max(0, selected - visible + 1)
                for index, row in enumerate(rows[start:start+visible], start):
                    attr = curses.A_REVERSE if index == selected else 0
                    if colored:
                        attr |= curses.color_pair(3 if row['stale'] else 2)
                    line(2 + index-start, overview(row), attr)
                top = 3 + visible
                titles = ('1 Betrieb', '2 Bindung', '3 Prüfung / Budget', '4 Fehler / Quellen')
                line(top, ' | '.join(('[' + title + ']') if i == tab else title for i, title in enumerate(titles)), curses.A_BOLD)
                if help_open:
                    content = ['Pfeile links/rechts: Instanz. Tab oder 1–4: Ansicht.',
                               'Pfeile hoch/runter, Bild hoch/runter: Details scrollen.',
                               'r: neu lesen, ?: Hilfe, q: Ende. Alle Abfragen sind lesend.',
                               'VERALTET zeigt gespeicherte Daten; daraus folgt kein aktiver Prozess.']
                else:
                    content = details(rows[selected], tab) if rows else ['Keine Instanzen']
                    content += ['Discovery: ' + str(error) for error in errors]
                offset = min(offset, max(0, len(content) - max(1, height-top-3)))
                for y, text in enumerate(content[offset:], top+1):
                    if y >= height-1:
                        break
                    line(y, text)
                line(height-1, '← → Instanz  ↑ ↓ Details  Tab/1–4 Ansicht  r Aktualisieren  ? Hilfe  q Ende')
            screen.refresh()
            key = screen.getch()
            if key in (ord('q'), 27):
                return 0
            if key == ord('r'):
                refresh.poll(force=True)
            elif key == ord('?'):
                help_open, offset = not help_open, 0
            elif key in (curses.KEY_LEFT, curses.KEY_RIGHT) and rows:
                selected = (selected + (1 if key == curses.KEY_RIGHT else -1)) % len(rows)
                offset = 0
            elif key == 9 or ord('1') <= key <= ord('4'):
                tab = (tab+1) % 4 if key == 9 else key-ord('1')
                offset = 0
            elif key in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_PPAGE, curses.KEY_NPAGE):
                offset = max(0, offset + {curses.KEY_UP: -1, curses.KEY_DOWN: 1,
                             curses.KEY_PPAGE: -10, curses.KEY_NPAGE: 10}[key])
    try:
        return curses.wrapper(display)
    finally:
        refresh.close()
