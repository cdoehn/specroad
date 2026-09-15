"""Shared invalid-command exception for data binding and declarations."""

class CommandUsageError(ValueError):
    """Invalid command declaration or invocation; nothing has been executed."""

