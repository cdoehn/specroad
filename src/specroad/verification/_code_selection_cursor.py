"""LF boundaries and lazy complete-window traversal, without hashing or I/O."""


def stored_line_span(text, start_line, end_line):
    """Return the stored character span and total lines, including missing ends.

    Only LF separates normalized lines. Other Unicode separators remain text.
    The caller retains the missing-range decision before encoding the selection.
    """
    offset = line_count = 0
    selected_start = selected_end = None
    while offset < len(text):
        line_count += 1
        if line_count == start_line:
            selected_start = offset
        newline = text.find('\n', offset)
        offset = len(text) if newline == -1 else newline + 1
        if line_count == end_line:
            selected_end = offset
    return selected_start, selected_end, line_count


def line_boundaries(content):
    """Index complete LF lines in normalized UTF-8, with no phantom final line."""
    boundaries = [0]
    offset = 0
    while offset < len(content):
        newline = content.find(b'\n', offset)
        offset = len(content) if newline == -1 else newline + 1
        boundaries.append(offset)
    return boundaries


def selection_span(boundaries, start, count):
    """Map an admitted complete window to a half-open byte span.

    A None boundary index denotes original bytes, otherwise start/count denote
    normalized lines. Availability is checked before calling this mapping.
    """
    return (boundaries[start], boundaries[start + count]) if boundaries is not None else (start, start + count)


def selection_windows(boundaries, size, count, exclude):
    """Yield complete candidates lazily, preserving overlap and traversal order."""
    for candidate in range(max(0, size - count + 1)):
        if candidate == exclude:
            continue
        left, right = selection_span(boundaries, candidate, count)
        yield candidate, left, right
