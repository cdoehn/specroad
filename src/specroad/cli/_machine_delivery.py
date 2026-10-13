"""Confirm every character of one materialized machine document and its flush."""


def write_machine_document(stream, document):
    """Honor text-stream short writes; never accept a stalled or false count.

    A failed destination may already contain a prefix. The caller reports an
    I/O failure and must not append a different result or claim full delivery.
    """
    value = document + '\n'
    offset = 0
    while offset < len(value):
        chunk = value[offset:offset + 65536]
        count = stream.write(chunk)
        if type(count) is not int or count <= 0 or count > len(chunk):
            raise OSError('Machine result delivery did not confirm progress')
        offset += count
    stream.flush()
