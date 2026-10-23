"""Shared RFC-4180 record bytes for already admitted text cells.

Cell types, character policies, headers and resource bindings belong to the
calling format adapter. This layer only quotes, frames and encodes text;
it does not infer, normalize, load or publish anything.
"""


def row_bytes(cells, *, quote_first=False):
    quoted = []
    for index, cell in enumerate(cells):
        if (any(c in cell for c in ',"\r\n') or (len(cells) == 1 and not cell)
                or (quote_first and index == 0)):
            cell = '"' + cell.replace('"', '""') + '"'
        quoted.append(cell)
    return (",".join(quoted) + "\r\n").encode("utf-8")
