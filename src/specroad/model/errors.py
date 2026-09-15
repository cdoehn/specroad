"""Structured model failures, independent of terminal presentation."""


class ModelError(ValueError):
    """No source contents are included in a public diagnostic."""

    def __init__(self, reason, *, path=None, pointer="", position=None,
                 line=None, column=None, highest_supported=None):
        super().__init__("Project data rejected: " + reason)
        self.reason = reason
        self.path = path
        self.pointer = pointer
        self.position = position
        self.line = line
        self.column = column
        self.highest_supported = highest_supported

    def diagnostic(self):
        return {"reason": self.reason, "path": self.path, "pointer": self.pointer,
                "position": self.position, "line": self.line, "column": self.column,
                "highest_supported": self.highest_supported}
