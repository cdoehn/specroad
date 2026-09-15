"""Controlled development-process environment; no global mutation."""

def test_environment(environment):
    result = dict(environment)
    for name in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTEST_CURRENT_TEST",
                 "PYTEST_XDIST_WORKER", "PYTEST_XDIST_WORKER_COUNT", "PYTEST_XDIST_TESTRUNUID"):
        result.pop(name, None)
    result["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    result["PYTHONDONTWRITEBYTECODE"] = "1"
    return result

