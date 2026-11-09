"""Compatibility exports for the shared standalone environment probe."""
import json

from verification_support.runtime_environment import environment, digest, probe, account


if __name__ == '__main__':
    print(json.dumps(probe(), sort_keys=True))
