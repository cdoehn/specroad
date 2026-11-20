"""Observed numeric runtime inventories; no project settings, paths or secrets."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import platform
import struct
import sys
import sysconfig

from ._values import decode, digest, encoded, require
from ._report_values import ENGINE_FACTS, engine_values
from ._text_policy import TEXT_POLICY_VERSION
from .registry import builtin_descriptor
from .requests import analyzer_binding


__all__ = ('numeric_inventory', 'EngineIdentity', 'engine_identity')

def _file_hash(path):
    value = sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def numeric_inventory(numpy):
    """Capture actual installed code and exposed numeric facts after model load.

    Optional/unavailable facts stay unknown. No environment dictionary or build
    paths are serialized; hashes describe local code without redistributing it.
    """
    try:
        core = numpy._core._multiarray_umath
        package = Path(numpy.__file__).resolve().parent
    except (OSError, AttributeError, TypeError, ValueError):
        return None, None
    try:
        runtime = encoded(dict(inventory_version='numeric-runtime-v1',
            implementation=sys.implementation.name, python_version=platform.python_version(),
            cache_tag=sys.implementation.cache_tag, executable_sha256=_file_hash(sys.executable),
            compiler=platform.python_compiler(), machine=platform.machine(), system=sys.platform,
            byteorder=sys.byteorder, pointer_bits=struct.calcsize('P') * 8,
            soabi=sysconfig.get_config_var('SOABI'), gil_disabled=bool(sysconfig.get_config_var('Py_GIL_DISABLED')),
            libc=list(platform.libc_ver()), float_info={name: str(getattr(sys.float_info, name)) for name in
                ('max', 'max_exp', 'min', 'min_exp', 'dig', 'mant_dig', 'epsilon', 'radix', 'rounds')}))
    except (OSError, AttributeError, TypeError, ValueError):
        runtime = None
    try:
        binaries = sorted(p for p in package.rglob('*') if p.is_file() and p.suffix in ('.so', '.pyd', '.dll'))
        vendor = package.with_name('numpy.libs')
        if vendor.is_dir():
            binaries += sorted(p for p in vendor.iterdir() if p.is_file())
        require(bool(binaries), 'analyzer_numeric_inventory_unavailable', exit_code=5)
        numeric = encoded(dict(inventory_version='numpy-runtime-v1', version=numpy.__version__,
            binaries=[dict(name=p.name, sha256=_file_hash(p)) for p in binaries],
            cpu_features={name: bool(value) for name, value in core.__cpu_features__.items()},
            cpu_baseline=list(core.__cpu_baseline__), cpu_dispatch=list(core.__cpu_dispatch__),
            float32={name: str(getattr(numpy.finfo(numpy.float32), name)) for name in ('bits', 'eps', 'tiny', 'max')},
            float64={name: str(getattr(numpy.finfo(numpy.float64), name)) for name in ('bits', 'eps', 'tiny', 'max')},
            error_policy=numpy.geterr(), buffer_size=int(numpy.getbufsize())))
    except (OSError, AttributeError, TypeError, ValueError):
        numeric = None
    return runtime, numeric


@dataclass(frozen=True)
class EngineIdentity:
    _engine: bytes
    _inventory: bytes

    @property
    def data(self):
        return decode(self._engine)

    @property
    def inventory(self):
        return decode(self._inventory)

    @property
    def sha256(self):
        return sha256(self._engine).hexdigest()

    @property
    def reproducible(self):
        return all(self.data[name]['value'] is not None for name in ENGINE_FACTS)


def engine_identity(engine):
    """Project owned observations into the closed T.4 engine contract."""
    values = dict(adapter_version='1.0.0',
        **{name: dict(value=None, reason='engine_not_loaded') for name in ENGINE_FACTS})
    inventories = dict(runtime=None, numpy=None)
    if engine is not None:
        facts = dict(library_versions=dict(engine.library_versions), model_sha256=engine.model_sha256,
            candidates=list(engine.candidates), candidates_sha256=engine.candidates_sha256,
            preprocessing_version=TEXT_POLICY_VERSION, unicode_version=engine.unicode_version)
        values['adapter_version'] = engine.adapter_version
        values.update({key: dict(value=value, reason=None) for key, value in facts.items()})
        for name in inventories:
            raw = getattr(engine, name + '_inventory')
            inventories[name] = None if raw is None else decode(raw)
            values[('runtime' if name == 'runtime' else 'numpy') + '_fingerprint'] = dict(
                value=None if raw is None else digest(inventories[name]),
                reason='numeric_inventory_unavailable' if raw is None else None)
    engine_values(values, analyzer_binding(builtin_descriptor(), ['language_detection']))
    return EngineIdentity(encoded(values), encoded(inventories))
