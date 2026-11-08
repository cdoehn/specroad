"""Shared, dependency-free CLI presentation for the local read-only helpers."""
import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import sys
import textwrap
import unicodedata

if __package__:
    from .availability import capture_native_file
else:
    from availability import capture_native_file


def safe_text(value):
    return ''.join(char if char.isprintable() else ' ' for char in str(value))


def number(value):
    return f'{value:,}'.replace(',', '.')


def cells(text):
    return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1
               for c in text)


def wrapped(text, width):
    """Wrap even long node IDs, without cutting ANSI sequences or wide glyphs."""
    words = re.findall(r'\s+|\S+', safe_text(text))
    line = ''
    spacing = ''
    for word in words:
        if word.isspace():
            spacing = word
            continue
        if line and cells(line) + cells(spacing) + cells(word) <= width:
            line += spacing + word
            spacing = ''
            continue
        if line:
            yield line
        line = ''
        spacing = ''
        for char in word:
            if line and cells(line) + cells(char) > width:
                yield line
                line = ''
            line += char
    if line:
        yield line


class Terminal:
    COLORS = {'title': '1;36', 'cyan': '36', 'green': '32', 'yellow': '33',
              'red': '1;31', 'dim': '2', 'bold': '1', 'magenta': '35'}

    def __init__(self, color='auto', plain=False, width=None, stream=None):
        stream = stream or sys.stdout
        self.color = not plain and (color == 'always' or color == 'auto'
            and stream.isatty() and os.environ.get('TERM') != 'dumb' and 'NO_COLOR' not in os.environ)
        self.unicode = not plain
        try:
            '╭─╮│╰╯●✓▰▱'.encode(stream.encoding or 'utf-8')
        except (UnicodeEncodeError, LookupError):
            self.unicode = False
        self.width = width or min(112, max(40, shutil.get_terminal_size((100, 24)).columns))
        self.lines = []

    def paint(self, value, style=''):
        text = safe_text(value)
        if not self.unicode:
            text = text.translate(str.maketrans({'·': '|', '→': '->', '—': '-', '–': '-'}))
        code = self.COLORS.get(style)
        return f'\033[{code}m{text}\033[0m' if self.color and code else text

    def line(self, value='', style='', indent=2):
        if not value:
            self.lines.append('')
        else:
            for part in wrapped(value, self.width - indent):
                self.lines.append(' ' * indent + self.paint(part, style))

    def header(self, title, target, repository=None):
        left, right, bottom_left, bottom_right, horizontal, vertical = (
            ('╭', '╮', '╰', '╯', '─', '│') if self.unicode else ('+', '+', '+', '+', '-', '|'))
        self.lines.append(self.paint(left + horizontal * (self.width - 2) + right, 'cyan'))
        for part in wrapped(f'SPECROAD  ·  {title}  /  {target.upper()}', self.width - 4):
            self.lines.append(self.paint(vertical, 'cyan') + ' ' + self.paint(part, 'title')
                              + ' ' * (self.width - cells(part) - 3) + self.paint(vertical, 'cyan'))
        self.lines.append(self.paint(bottom_left + horizontal * (self.width - 2) + bottom_right, 'cyan'))
        if repository:
            self.line(repository, 'dim')

    def section(self, title):
        self.line()
        prefix = '──' if self.unicode else '--'
        self.line(prefix + ' ' + title, 'title', indent=0)

    def status(self, label, style='cyan'):
        self.line(('● ' if self.unicode else '* ') + label, style)

    def progress(self, done, total, style='cyan'):
        fraction = min(1, max(0, done / total)) if total else 0
        width = max(10, min(32, self.width - 32))
        filled = round(width * fraction)
        on, off = ('▰', '▱') if self.unicode else ('#', '-')
        self.line(f'[{on * filled}{off * (width - filled)}] {number(done)} / {number(total)} · {fraction:.1%}', style)

    def warnings(self, values):
        if values:
            self.section('Hinweise')
            for value in values:
                self.line('! ' + value, 'yellow')

    def __str__(self):
        return '\n'.join(self.lines)


def width_value(value):
    try:
        width = int(value)
        if not 40 <= width <= 240:
            raise ValueError
        return width
    except ValueError:
        raise argparse.ArgumentTypeError('Breite muss zwischen 40 und 240 liegen.') from None


class HelperParser(argparse.ArgumentParser):
    def format_help(self):
        raw = super().format_help()
        args = self.display_args
        mode = 'auto'
        for i, value in enumerate(args):
            if value == '--color' and i + 1 < len(args):
                mode = args[i + 1]
            elif value.startswith('--color='):
                mode = value.split('=', 1)[1]
            elif value == '--no-color':
                mode = 'never'
        ui = Terminal(mode, '--plain' in args or '--json' in args)
        ui.header(self.display_title, 'CLI')
        lines = [str(ui), '']
        for line in raw.splitlines():
            style = 'title' if line.endswith(':') else 'cyan' if line.startswith('usage:') else ''
            lines.append(ui.paint(line, style))
        return '\n'.join(lines) + '\n'


def parser_for(title, description, argv, examples):
    parser = HelperParser(description=description, add_help=False,
                          formatter_class=argparse.RawDescriptionHelpFormatter,
                          epilog='Beispiele:\n' + textwrap.indent(examples, '  ')
                          + '\n\nStandardziel: diese Repository-Kopie. Pfadoptionen überschreiben nur die Anzeige.'
                          + '\nNur lesend: keine Tests, Dienste oder Apply-Aufrufe.')
    parser.display_title = title
    parser.display_args = list(sys.argv[1:] if argv is None else argv)
    parser._optionals.title = 'Optionen'
    parser.add_argument('-h', '--help', action='help', help='diese Hilfe anzeigen und beenden')
    sources = parser.add_argument_group('Datenquellen (optional)')
    sources.add_argument('--apply-dir', type=Path, metavar='PFAD',
                         help='Berichte einer anderen Apply-Kopie lesen')
    sources.add_argument('--database', type=Path, metavar='DATEI',
                         help='explizite SQLite-Laufzeitdatenbank lesen; ändert keinen Schreiber')
    display = parser.add_argument_group('Darstellung')
    display.add_argument('--json', action='store_true', help='maschinenlesbar, immer ohne Farben')
    display.add_argument('--color', choices=('auto', 'always', 'never'), default='auto',
                         help='Farben: auto (Terminal), always (auch watch -c), never')
    display.add_argument('--no-color', dest='color', action='store_const', const='never', help='Farben ausschalten')
    display.add_argument('--plain', action='store_true', help='schlicht, ohne Farben und grafische Zeichen')
    display.add_argument('--width', type=width_value, help='Ausgabebreite 40–240 (sonst automatisch)')
    return parser


def terminal(args):
    return Terminal(args.color, args.plain or args.json, args.width)


@dataclass(frozen=True)
class Target:
    invoked_repository: Path
    repository: Path
    exchange: Path
    database_override: Path | None = None
    apply_override: bool = False

    @classmethod
    def from_repository(cls, repository, *, apply_directory=None, database=None):
        repository = Path(repository).resolve()
        override = Path(apply_directory).expanduser().resolve() if apply_directory is not None else None
        database = Path(database).expanduser().resolve() if database is not None else None
        source = override or repository
        if override is not None and not override.is_dir():
            raise ValueError(f'Apply-Verzeichnis fehlt: {override}')
        if database is not None and not database.is_file():
            raise ValueError(f'Explizite Laufzeitdatenbank fehlt: {database}')
        pairs = {'specroad-codex': 'specroad-apply', 'specroad-dev': 'specroad-apply',
                 'specroad-dev2': 'specroad-apply2', 'specroad-apply': 'specroad-apply',
                 'specroad-apply2': 'specroad-apply2'}
        name = source.name if override is not None else pairs.get(source.name)
        if name in ('specroad-apply', 'specroad-apply2'):
            apply = source.parent / name
            exchange = source.parent / ('exchange2' if name.endswith('2') else 'exchange')
        elif (source / '.patchharbor/id').is_file() or (source / '.patchharbor/config.json').is_file():
            # A differently named registered Apply carries its own explicit target.
            config = source / '.patchharbor/config.json'
            value = json.loads(capture_native_file(config, 65536))
            directory = value.get('exchange_directory') if isinstance(value, dict) else None
            if not isinstance(directory, str) or not Path(directory).is_absolute():
                raise ValueError('Registrierte Apply-Kopie ohne eindeutigen Exchange.')
            apply, exchange = source, Path(directory)
        elif override is not None and database is not None:
            apply, exchange = override, database.parent
        else:
            raise ValueError('Keine eindeutige Apply-Zuordnung für diese Repository-Kopie. '
                             'Passende Kopie aufrufen oder --apply-dir und --database angeben.')
        return cls(repository, apply.resolve(), exchange.resolve(), database, override is not None)

    @property
    def name(self):
        return self.repository.name.removeprefix('specroad-')

    @property
    def root(self):
        return self.invoked_repository.parent

    @property
    def database(self):
        return self.database_override or self.exchange / 'specroad-test-runtime-history.sqlite3'

    def metadata(self):
        return {'target': self.name, 'repository': str(self.repository),
                'invoked_repository': str(self.invoked_repository),
                'exchange': str(self.exchange), 'database': str(self.database),
                'database_explicit': self.database_override is not None,
                'apply_directory_explicit': self.apply_override}

    def runtime_ready(self):
        """Never silently substitute another lane's database during migration."""
        if self.database_override is not None:
            return True, 'Explizite Datenquelle gewählt; die Konfiguration des Testschreibers bleibt unverändert.'
        policy = self.repository / 'verification/test_runtime_policy.json'
        if not policy.is_file():
            return False, 'Keine Testlaufzeit-Policy vorhanden; Schreibziel noch nicht bestätigt.'
        value = json.loads(capture_native_file(policy, 65536))
        if (not isinstance(value, dict) or set(value) != {'format_version', 'selection', 'database'}
                or type(value.get('format_version')) is not int
                or value['format_version'] != 1 or value.get('selection') != 'latest_valid_fifth'):
            raise ValueError('Unbekanntes Format der Testlaufzeit-Policy.')
        declared = value.get('database')
        if declared == 'patchharbor-exchange':
            config = self.repository / '.patchharbor/config.json'
            if not config.is_file():
                return False, 'PatchHarbor-Exchange ist für dieses Ziel noch nicht konfiguriert.'
            native = json.loads(capture_native_file(config, 65536))
            if (not isinstance(native, dict) or type(native.get('format_version')) is not int
                    or native['format_version'] != 1):
                raise ValueError('Unbekanntes Format der PatchHarbor-Konfiguration.')
            exchange = native.get('exchange_directory')
            actual = Path(exchange) / self.database.name if isinstance(exchange, str) and Path(exchange).is_absolute() else None
        else:
            actual = self.repository / declared if isinstance(declared, str) else None
        if actual is None or actual.resolve() != self.database:
            return False, ('Testschreiber noch nicht auf den eigenen Exchange umgestellt. '
                           'Fremde Laufzeitdaten werden nicht angezeigt.')
        return True, None


def error_output(args, title, error):
    message = safe_text(error)
    target = getattr(args, 'target', 'REPOSITORY')
    if args.json:
        return json.dumps({'status': 'unavailable', 'target': target, 'error': message}, ensure_ascii=False)
    ui = terminal(args)
    ui.header(title, target)
    ui.status('Nicht verfügbar', 'red')
    ui.line(message)
    return str(ui)
