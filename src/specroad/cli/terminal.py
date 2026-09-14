"""Terminal policy and line layout, replaceable without touching domain results."""

from dataclasses import dataclass
import os
import textwrap
import unicodedata


def _is_tty(stream):
    try:
        return bool(getattr(stream, "isatty", lambda: False)())
    except (OSError, ValueError):
        return False


def _supports_symbols(stream):
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        "✓↻│─◌×".encode(encoding)
    except (UnicodeError, LookupError):
        return False
    return True


@dataclass(frozen=True)
class DisplayPolicy:
    color: bool
    width: int
    unicode: bool
    quiet: bool

    @classmethod
    def from_streams(cls, out, err, *, no_color=False, quiet=False):
        color = _is_tty(out) and not no_color and "NO_COLOR" not in os.environ
        try:
            columns = os.get_terminal_size(out.fileno()).columns if _is_tty(out) else 76
        except (AttributeError, OSError, ValueError):
            columns = 76
        return cls(color, max(32, min(100, columns)),
                   _supports_symbols(out) and _supports_symbols(err), bool(quiet))


def _safe(value):
    # Project data cannot inject terminal-control or bidi-control sequences.
    return "".join(char if char in "\n\t" or unicodedata.category(char) not in ("Cc", "Cf")
                   else "?" for char in str(value))


class TerminalWriter:
    def __init__(self, policy: DisplayPolicy):
        self.policy = policy

    def _paint(self, text, style):
        colors = {"title": "1;36", "success": "1;32", "warning": "1;33", "error": "1;31", "muted": "2", "phase": "36"}
        return "\033[" + colors[style] + "m" + text + "\033[0m" if self.policy.color else text

    def line(self, stream, text="", *, style=None, prefix=""):
        width = max(12, self.policy.width - len(prefix))
        lines = _safe(text).splitlines() or [""]
        for line in lines:
            for wrapped in textwrap.wrap(line, width=width, replace_whitespace=False, drop_whitespace=False) or [""]:
                value = prefix + wrapped
                stream.write((self._paint(value, style) if style else value) + "\n")
        stream.flush()
