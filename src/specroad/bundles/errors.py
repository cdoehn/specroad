"""Machine-readable bundle failures, without source contents or presentation."""


class BundleError(ValueError):
    def __init__(self, reason, *, code='SRV002', exit_code=3):
        super().__init__(reason)
        self.reason, self.code, self.exit_code = reason, code, exit_code

    def as_dict(self):
        return {'reason': self.reason, 'code': self.code, 'exit_code': self.exit_code}
