"""Deterministic bytes and exclusive atomic publication for the language add-on."""
import json
import os
from pathlib import Path
import tempfile
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('utf-8')


def publish_archive(payload, output):
    output = Path(output).absolute()
    if os.path.lexists(output):
        raise FileExistsError(output)
    parent = output.parent.resolve(strict=True)
    output = parent / output.name
    descriptor, name = tempfile.mkstemp(prefix='.language-package-', dir=parent)
    temp = Path(name)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            with ZipFile(stream, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
                for path, raw in sorted(payload.items()):
                    info = ZipInfo(path, (1980, 1, 1, 0, 0, 0))
                    info.compress_type = ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temp, output)  # Exclusive atomic publication, never replace.
        directory = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temp.unlink(missing_ok=True)
    return output
