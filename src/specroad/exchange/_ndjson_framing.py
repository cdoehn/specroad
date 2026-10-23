"""LF byte framing only: no JSON decoding, native fields or publication."""
from ..model.errors import ModelError


def _parts(raw):
    """Yield byte spans and whether LF terminated them; a block is not EOF."""
    start = 0
    while start < len(raw):
        end = raw.find(b"\n", start)
        if end < 0:
            yield raw[start:], False
            return
        yield raw[start:end], True
        start = end + 1


def iter_lines(raw):
    """Physical lines from an explicitly complete source, including blanks."""
    for line, (record, _) in enumerate(_parts(raw), 1):
        yield record, line


def check_line(record):
    """The LF transport profile never admits raw CR, even inside a string."""
    if b"\r" in record:
        raise ModelError("ndjson_raw_cr")


class LineFramer:
    """Unfinished bytes and physical position, independent of object validity.

    A terminated line remains current until its consumer accepts it by
    advancing the iterator. Failed validation therefore retains its position
    and pending bytes. Only explicit caller EOF may consume an unfinished tail.
    """

    def __init__(self):
        self.pending = bytearray()
        self.line = 1

    def feed(self, block):
        for part, terminated in _parts(block):
            self.pending.extend(part)
            if terminated:
                yield bytes(self.pending), self.line
                self.pending.clear()
                self.line += 1
