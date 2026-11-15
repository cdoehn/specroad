"""Portable paths and exact byte identities for read-only qualification."""
from hashlib import sha256
from pathlib import PurePosixPath
import unicodedata
from ..model.paths import project_path
from .errors import QualificationError, require


def safe_path(value):
    try:
        return project_path(value)
    except Exception as error:
        from ..model.errors import ModelError
        if not isinstance(error, ModelError):
            raise
        raise QualificationError('restore_unsafe_path', exit_code=7) from error


def root_path(value):
    require(type(value) is str and value.startswith('/') and str(PurePosixPath(value)) == value
            and not value.startswith('//'), 'restore_canonical_root_required', exit_code=7)
    if value != '/':
        safe_path(value[1:])
    return value


def namespace(paths):
    """Files and directories share the same portable, case-insensitive space."""
    aliases = {}
    for path in paths:
        safe_path(path)
        for i in range(1, len(path.split('/')) + 1):
            prefix = '/'.join(path.split('/')[:i])
            alias = unicodedata.normalize('NFC', prefix).casefold()
            require(alias not in aliases or aliases[alias] == prefix,
                    'restore_path_collision', exit_code=7)
            aliases[alias] = prefix


def file_row(path, raw):
    return {'path': path, 'size': len(raw), 'sha256': sha256(raw).hexdigest()}
