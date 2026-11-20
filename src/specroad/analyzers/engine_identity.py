"""Observed numeric runtime inventories; no project settings, paths or secrets."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import platform
import struct
import sys
import sysconfig

from ._values import AnalyzerError, decode, digest, encoded, require
from ._report_values import ENGINE_FACTS, engine_values
from ._text_policy import TEXT_POLICY_VERSION
from .registry import builtin_descriptor
from .requests import analyzer_binding
from .requests import AnalyzerRequest


__all__ = ('numeric_inventory', 'EngineIdentity', 'engine_identity', 'EngineBinding', 'bind_engine')

def _loaded_numeric_runtime():
    """Observe already mapped numeric libraries, never load a project plugin."""
    import ctypes
    import os
    names = ('libpython', 'libc.', 'libm.', 'ld-linux', 'libopenblas', 'libscipy_openblas',
             'libgfortran', 'libquadmath', 'libomp', 'libgomp', 'libiomp', 'libmkl')
    paths = set()
    for line in Path('/proc/self/maps').read_text().splitlines():
        fields = line.split(None, 5)
        if len(fields) == 6 and fields[5].startswith('/'):
            path = Path(fields[5])
            if path.name.startswith(names):
                paths.add(path)
    require(bool(paths), 'analyzer_numeric_inventory_unavailable', exit_code=5)
    libraries, threads = [], []
    for path in sorted(paths, key=lambda p: p.name):
        libraries.append(dict(name=path.name, sha256=_file_hash(path)))
        if 'openblas' in path.name:
            library = ctypes.CDLL(str(path), mode=os.RTLD_NOLOAD | os.RTLD_LOCAL)
            count = None
            for name in ('scipy_openblas_get_num_threads64_', 'scipy_openblas_get_num_threads',
                         'openblas_get_num_threads64_', 'openblas_get_num_threads'):
                function = getattr(library, name, None)
                if function is not None:
                    function.argtypes, function.restype = [], ctypes.c_int
                    count = function()
                    break
            require(type(count) is int and count > 0, 'analyzer_numeric_inventory_unavailable', exit_code=5)
            observed = {}
            for stem in ('get_config', 'get_corename'):
                answer = None
                for prefix in ('scipy_openblas_', 'openblas_'):
                    for suffix in ('64_', '_64_', ''):
                        function = getattr(library, prefix + stem + suffix, None)
                        if function is not None:
                            function.argtypes, function.restype = [], ctypes.c_char_p
                            raw = function()
                            answer = raw.decode('ascii') if raw is not None else None
                            break
                    if answer is not None:
                        break
                require(type(answer) is str and bool(answer), 'analyzer_numeric_inventory_unavailable', exit_code=5)
                observed[stem] = answer
            threads.append(dict(library_sha256=libraries[-1]['sha256'], thread_count=count,
                                configuration=observed['get_config'], core=observed['get_corename']))
    require(bool(threads), 'analyzer_numeric_inventory_unavailable', exit_code=5)
    rounding = ctypes.CDLL(None).fegetround
    rounding.argtypes, rounding.restype = [], ctypes.c_int
    mode = rounding()
    require(mode >= 0, 'analyzer_numeric_inventory_unavailable', exit_code=5)
    return dict(libraries=sorted(libraries, key=lambda v: (v['name'], v['sha256'])),
                blas_threads=sorted(threads, key=lambda v: v['library_sha256']), floating_point_rounding=mode)


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
            libc=list(platform.libc_ver()), loaded_numeric_runtime=_loaded_numeric_runtime(),
            float_info={name: str(getattr(sys.float_info, name)) for name in
                ('max', 'max_exp', 'min', 'min_exp', 'dig', 'mant_dig', 'epsilon', 'radix', 'rounds')}))
    except (AnalyzerError, OSError, AttributeError, TypeError, ValueError):
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
    except (AnalyzerError, OSError, AttributeError, TypeError, ValueError):
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
        if inventories['runtime'] is not None:
            require(inventories['runtime'].get('inventory_version') == 'numeric-runtime-v1'
                    and inventories['runtime'].get('implementation') == engine.python_implementation
                    and inventories['runtime'].get('python_version') == engine.python_version,
                    'analyzer_runtime_inventory_mismatch', exit_code=6)
        if inventories['numpy'] is not None:
            require(inventories['numpy'].get('inventory_version') == 'numpy-runtime-v1'
                    and inventories['numpy'].get('version') == dict(engine.library_versions).get('numpy'),
                    'analyzer_numpy_inventory_mismatch', exit_code=6)
    engine_values(values, analyzer_binding(builtin_descriptor(), ['language_detection']))
    return EngineIdentity(encoded(values), encoded(inventories))


@dataclass(frozen=True)
class EngineBinding:
    _encoded: bytes

    @property
    def data(self):
        return decode(self._encoded)

    def require_current(self, request, engine):
        actual = bind_engine(request, engine)
        require(actual._encoded == self._encoded, 'analyzer_engine_binding_changed', exit_code=6)


def bind_engine(request, engine):
    """A JSON-only continuation binding, never a serialized model or checkpoint."""
    require(type(request) is AnalyzerRequest, 'analyzer_request_required', exit_code=2)
    identity = engine_identity(engine)
    require(identity.reproducible, 'analyzer_engine_identity_unavailable', exit_code=5)
    matches = [entry for entry in request.data['analyzers'] if entry['descriptor'] == builtin_descriptor().data]
    require(len(matches) == 1, 'analyzer_reference_not_requested', exit_code=2)
    return EngineBinding(encoded(dict(binding_version='language-engine-v1', **request.binding,
        analyzer=matches[0], engine_sha256=identity.sha256)))
