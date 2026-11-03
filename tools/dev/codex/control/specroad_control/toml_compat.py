"""Stdlib TOML on modern Python; development backport for the Python 3.10 matrix."""
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
