"""Shared import guard source for isolated Core and zipapp subprocesses."""

# Keep the child independent of the test package and its installed dependencies.
# CPython 3.10/3.11 copy probes Jython's optional org.python.core and catches
# ImportError. Report that root as absent, never load it from a search path.
# Other non-Core, non-stdlib imports remain hard failures, even when a caller
# would swallow ImportError for an optional dependency.
CORE_STDLIB_IMPORT_GUARD = """\
import sys
class OnlyCoreAndStdlib:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'org':
            raise ModuleNotFoundError("No module named 'org'", name=fullname)
        if fullname.split('.')[0] not in sys.stdlib_module_names | {'specroad'}:
            raise AssertionError('third-party import attempted: ' + fullname)
sys.meta_path.insert(0, OnlyCoreAndStdlib())
"""
