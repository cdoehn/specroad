"""Compatibility import for the passive completed-bootstrap reader."""
from .bootstrap_completion import _read, read_completed_bootstrap
recover_bootstrap = read_completed_bootstrap
