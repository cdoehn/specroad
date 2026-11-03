class ControlError(Exception):
    """Stable, machine-readable failure classification, without configuration values."""
    def __init__(self, code: str, message: str, *, details=None):
        self.code = code
        self.details = dict(details or {})
        super().__init__(message)
