"""Owned temporary models and test publishers, not a production write backend."""
from contextlib import contextmanager
from pathlib import Path
from specroad.changes import (PublicationAuthority, TargetModel, project_lock,
    prepare_publication_check, publish_after_recheck, PublicationReceipt, ChangeBackend)
from specroad.model.model_manifest import ProjectReadBinding
from specroad.validation import ModelDocument
from .targets import model, plan, POLICY
from .folds import goal, edit

ALLOW = PublicationAuthority('test-human-authorizer', '1', lambda request: True)
TRANSACTION = 'txn-publish-test'


def prepared(root, *, operations=None, artifacts=None):
    root = Path(root).resolve()
    if not root.exists():
        root.mkdir(parents=True)
    inode = root.stat()
    m = model(artifacts or [goal()], binding=ProjectReadBinding('sample', str(root), (inode.st_dev,inode.st_ino)))
    for p,b in m.source_files.items():
        f=root/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b)
    ops=operations if operations is not None else [edit(m.artifacts[0], 'Changed')]
    p=plan(m, ops)
    return m,p,prepare_publication_check(p,m,policy=POLICY)


def options(check):
    return dict(kind='writer', command='change apply', project_id='sample',
                request_id=check.request.data['request_id'], transaction_id=TRANSACTION)


def invoke(check, held, publish, *, authority=ALLOW, **kw):
    return publish_after_recheck(check,check.request,held_lock=held,
            transaction_id=TRANSACTION,authority=authority,publish=publish,**kw)


def files(root):
    # Operational lock/audit files are not normative model files.
    return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*')
            if p.is_file() and '.specroad' not in p.relative_to(root).parts}


class NativeGuardStorage:
    """Test-only writes under a real native lock; NO journal or fsync promise."""
    def __init__(self, m, check):
        self.root=Path(m.binding.source_root);self.model=m;self.check=check;self.calls=[]

    @contextmanager
    def transaction(self, request):
        with project_lock(self.root, **options(self.check)) as self.held:
            yield self

    def read_model(self):
        base=self.model
        self.model=TargetModel((self.root/'specroad.json').read_bytes(),base.binding,
            [ModelDocument(d.path,(self.root/d.path).read_bytes()) for d in base.documents],
            profile=base.profile,resource_files=[ModelDocument(d.path,(self.root/d.path).read_bytes())
                for d in base.resource_files], attachments=base.attachment_descriptors,
            language_packages=base.language_packages,**base.reservations)
        return self.model

    def publish(self, request):
        def action(r):
            self.calls.append(r.sha256)
            for d in r.documents:
                f=self.root/d.path;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(d.content)
            v=r.data
            return PublicationReceipt(r.sha256,v['target_root_sha256'],v['request_id'],
                tuple(v['changed_paths']),'test-receipt')
        return publish_after_recheck(self.check,request,held_lock=self.held,
            transaction_id=TRANSACTION,authority=ALLOW,publish=action)

    @property
    def backend(self):
        return ChangeBackend('test-native-guard', '1', self.transaction)
