"""Cancellation RPC over an already checked host gateway; no new SSH login."""
import execnet

from .attempt_supervisor import request


def cancel_remote(active, ready, rows, profile, group):
    binding = ready[active['worker']]
    row = rows[active['worker']]
    spec = execnet.XSpec(row['spec'])
    if spec.via:
        gateway = group[spec.via]
        channel = gateway.remote_exec("""import sys
root,endpoint,secret,token=channel.receive()
sys.path.insert(0,root+'/tools')
from dev.test_hosts.attempt_supervisor import request
from dev.test_hosts.environment import environment,digest
from dev.test_hosts.snapshot import inventory,fingerprint
from verification_support.identity import source_identity
reply=request(endpoint,secret,'cancel',token=token)
reply['binding']={'source_sha256':source_identity(root),'snapshot_sha256':fingerprint(inventory(root)),'environment_sha256':digest(environment())}
channel.send(reply)
""")
        channel.send((row['root'], binding['endpoint'], binding['secret'], active['token']))
        reply = channel.receive(timeout=20)
    else:
        from .environment import environment, digest
        from .snapshot import inventory, fingerprint
        from verification_support.identity import source_identity
        reply = request(binding['endpoint'], binding['secret'], 'cancel', token=active['token'])
        reply['binding'] = dict(source_sha256=source_identity(row['root']),
            snapshot_sha256=fingerprint(inventory(row['root'])), environment_sha256=digest(environment()))
    if reply['binding'] != dict(source_sha256=profile['source_sha256'], snapshot_sha256=profile['snapshot_sha256'], environment_sha256=row['environment_sha256']):
        raise ValueError('Source or environment changed before cancellation confirmation')
    return reply
