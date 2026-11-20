"""Single explicit worker inventory capture; imports never load NumPy or a model."""
from hashlib import sha256
from pathlib import Path
import platform
import struct
import sys
import sysconfig

from ._values import AnalyzerError, encoded, require


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
