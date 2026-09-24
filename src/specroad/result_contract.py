"""Shared invalid-result contract, independent of command parsing or rendering."""


class ResultContractError(ValueError):
    """A trusted handler attempted to return an invalid or unsupported result."""
