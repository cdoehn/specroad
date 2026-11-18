"""Explicit synthetic host authority; production authority is never inferred."""
from hashlib import sha256
from pathlib import Path

from support.transport_outbound import child
from support.transport_return import origin, sandbox, offline_export


def returned(root, distribution, *, subproject=False):
    host=root/'host';host.mkdir()
    handoff=origin(host,distribution,subproject=subproject)
    remote=root/'remote';remote.mkdir()
    value,proposal=sandbox(remote,distribution,handoff)
    result=offline_export(remote,distribution[1],value)
    assert result['code']==0,result
    return handoff,Path(result['outcome']['result']['file']['path']),proposal


def receive(handoff, package, distribution, *, name='receive', before='', after='', allow=True, transport_allow=True):
    root=handoff['repository'].parent
    options=dict(expected_sha256=sha256(package.read_bytes()).hexdigest(),
        reference=str(handoff['source']),reference_sha256=sha256(handoff['source'].read_bytes()).hexdigest(),
        repository=str(handoff['repository']),workspace=str(root/name),patchharbor_pyz=str(handoff['runtime']),
        patchharbor_pyz_sha256=sha256(handoff['runtime'].read_bytes()).hexdigest(),timeout=120)
    script='''
from pathlib import Path
import json
from specroad.changes import PublicationAuthority
from specroad.transport.return_receive import ReturnReceiver
from specroad.transport.snapshots import TransportFailure
from specroad.model.errors import ModelError
from specroad.security import SafetyViolation
options='''+repr(options)+'''
package=Path('''+repr(str(package))+''')
authority=PublicationAuthority('synthetic-local-receive-test','1',lambda request: '''+repr(allow)+''')
'''+before+'''
try:
    receiver=ReturnReceiver(package,authority=authority,authorize_transport=lambda request: '''+repr(transport_allow)+''',**options)
    result=receiver.receive()
except (TransportFailure,ModelError,SafetyViolation,OSError) as error:
    result={'status':'refused','reason':getattr(error,'reason',type(error).__name__),
            'exit_code':getattr(error,'exit_code',7)}
'''+after+'''
print(json.dumps(result))
'''
    return child(root,script,source=distribution)
