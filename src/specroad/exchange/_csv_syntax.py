"""RFC-4180 UTF-8 field syntax; no sniffing, conversion, or file access."""
from ..mappings.csv_profile import CSVError


def read_rows(raw):
    """Internal iterator; callers publish only after consuming the entire input."""
    if type(raw) is not bytes:
        raise CSVError("csv_bytes_required")
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        raise CSVError("csv_invalid_utf8") from None
    if text.startswith("\ufeff"):
        text = text[1:]
    if not text:
        raise CSVError("csv_header_required", record=1)
    row, field = [], []
    state, position, record = "start", 0, 1
    while position < len(text):
        char = text[position]
        column = len(row) + 1
        if (ord(char) < 32 and char not in "\r\n") or char == "\x7f":
            raise CSVError("csv_invalid_character", record=record, column=column)
        if state == "quoted":
            if char == '"':
                state = "closed"
            else:
                field.append(char)
        elif char == '"':
            if state == "start":
                state = "quoted"
            elif state == "closed":
                field.append(char)
                state = "quoted"
            else:
                raise CSVError("csv_invalid_quote", record=record, column=column)
        elif char == ",":
            row.append("".join(field))
            field, state = [], "start"
        elif char in "\r\n":
            if char != "\r" or text[position:position + 2] != "\r\n":
                raise CSVError("csv_record_separator", record=record, column=column)
            yield row + ["".join(field)]
            row, field, state = [], [], "start"
            record += 1
            position += 1
        elif state == "closed":
            raise CSVError("csv_after_quote", record=record, column=column)
        else:
            field.append(char)
            state = "plain"
        position += 1
    if state == "quoted":
        raise CSVError("csv_unclosed_quote", record=record, column=len(row) + 1)
    if row or state != "start":
        yield row + ["".join(field)]


def write_row(cells, *, header=False):
    quoted = []
    for index, cell in enumerate(cells):
        if any((ord(c) < 32 and c not in "\r\n") or c == "\x7f" for c in cell):
            raise CSVError("csv_unrepresentable_character", column=index + 1)
        if (any(c in cell for c in ',"\r\n') or (len(cells) == 1 and not cell)
                or (header and index == 0 and cell.startswith("\ufeff"))):
            cell = '"' + cell.replace('"', '""') + '"'
        quoted.append(cell)
    return (",".join(quoted) + "\r\n").encode("utf-8")
