"""Apply overview presentation; no data reads, curses imports or state changes."""
from .cli import cells, safe_text

STATES = {'free': 'FREI', 'busy': 'BELEGT', 'unknown': 'UNKLAR',
          'missing': 'FEHLT', 'unregistered': 'NICHT REGISTRIERT'}


def source(target, name):
    return target[name]['data'] or {}


def report(target):
    return source(target, 'status').get('report', {})


def freshness(target):
    stale = [name for name in ('status', 'history') if target[name]['stale']]
    if stale:
        return 'VERALTET: ' + ', '.join(stale)
    return 'lädt …' if any(target[s]['refreshing'] for s in ('status', 'history')) else 'gelesen'


def progress_counts(target):
    counts = report(target).get('tests') or {}
    ended, total = counts.get('ended'), counts.get('total')
    if type(ended) is int and type(total) is int and 0 <= ended <= total and total > 0:
        return ended, total
    return None


def progress_active(target):
    view = report(target)
    run = (view.get('tests') or {}).get('run') or {}
    return (not target['status']['stale'] and view.get('availability', {}).get('state') == 'busy'
            and view.get('phase') == 'testing' and bool(run) and not run.get('finished')
            and progress_counts(target) is not None)


def overview_parts(target):
    view = report(target)
    counts = view.get('tests') or {}
    state = STATES.get(view.get('availability', {}).get('state'), 'LÄDT')
    if target['status']['stale']:
        state = 'UNKLAR (alter Stand)'
    failed = counts.get('failed', 0)
    error = (f' · FEHLER {failed}' if type(failed) is int and failed > 0
             else ' · FEHLER' if view.get('phase') == 'failed' else '')
    run = counts.get('run') or {}
    progress = f'{counts.get("ended", 0)}/{counts.get("total", "?")}' if counts else '—'
    completed = progress_counts(target)
    if completed is not None:
        ended, total = completed
        percent = 100.0 if ended == total else min(99.9, 100 * ended / total)
        progress += f' · {percent:.1f} %'
    return ((f'{target["repository"].rsplit("/", 1)[-1]:<21} {state}', False),
            (error, True), (' ' * max(1, 24 - cells(state + error)), False),
            (f'Bundle {view.get("bundle") or "—":>4}  {view.get("phase", view.get("status", "")):<12} '
             f'{progress:>12}  {run.get("workers", "—")} W  {freshness(target)}', False))


def overview(target):
    return ''.join(text for text, _ in overview_parts(target))


def init_overview_colors(curses, colored):
    if not colored or curses.COLOR_PAIRS <= 8:
        return False
    try:
        for pair, foreground, background in (
                (5, curses.COLOR_BLACK, curses.COLOR_GREEN),
                (6, curses.COLOR_BLACK, curses.COLOR_YELLOW),
                (7, curses.COLOR_RED, curses.COLOR_GREEN),
                (8, curses.COLOR_RED, curses.COLOR_YELLOW)):
            curses.init_pair(pair, foreground, background)
    except curses.error:
        return False  # keep ordinary foreground colours and numeric progress
    return True


def overview_spans(parts, width, filled, color):
    """Clip by terminal cells and keep combining characters with their base."""
    column, start, previous, text = 1, 1, None, ''
    for fragment, failed in parts:
        for char in safe_text(fragment):
            size = cells(char)
            if column + size > width - 1:
                if text:
                    yield start, text, previous
                return
            if size == 0 and text:
                text += char
                continue
            current = (5 if column < filled else 6) if filled is not None else color
            if failed:
                current = current + 2 if filled is not None else 4
            if current != previous:
                if text:
                    yield start, text, previous
                start, previous, text = column, current, ''
            text += char
            column += size
    if text:
        yield start, text, previous


def draw_overview(screen, y, target, curses, *, colored, progress_colors, selected, focused):
    height, width = screen.getmaxyx()
    if y < 0 or y >= height - 1 or width < 3:
        return
    availability = report(target).get('availability', {}).get('state')
    color = 3 if target['status']['stale'] else 2 if availability == 'free' else 3 if availability in ('unknown', 'busy') else 1
    filled = None
    if progress_colors and progress_active(target):
        ended, total = progress_counts(target)
        filled = width * ended // total
    emphasis = curses.A_BOLD if focused else 0
    parts = (('› ' if selected else '  ', False),) + overview_parts(target)
    try:
        if filled is not None:
            # Fill even unused cells and the last terminal column. Painting text
            # afterwards avoids splitting a wide glyph with an attribute change.
            screen.hline(y, 0, ord(' '), width, curses.color_pair(6) | emphasis)
            if filled:
                screen.hline(y, 0, ord(' '), filled, curses.color_pair(5) | emphasis)
        for column, text, pair in overview_spans(parts, width, filled, color):
            attr = (curses.color_pair(pair) if colored else 0) | emphasis
            if pair in (4, 7, 8):
                attr |= curses.A_BOLD
            screen.addstr(y, column, text, attr)
    except (curses.error, UnicodeError):
        pass  # resize/unsupported glyph: the next frame uses current dimensions
