"""Synchronous test storage, NOT a shipping transaction/authorization backend."""
from contextlib import contextmanager
from specroad.changes import ChangeBackend, PublicationReceipt, TargetModel
from specroad.validation import ModelDocument
from .targets import ACTOR, TIME, SCOPE

FIELDS = dict(change_plan_id='CP-explicit', request_id='request-1', actor=ACTOR,
              planned_at=TIME, scope_descriptor=SCOPE, metadata_policy_version='change-metadata-v1')


def rebuild(base, *, documents=None, **kw):
    options = dict(profile=base.profile, resource_files=base.resource_files,
        attachments=base.attachment_descriptors, language_packages=base.language_packages,
        **base.reservations)
    options.update(kw)
    binding = options.pop('binding', base.binding)
    config = options.pop('configuration_bytes', base.configuration_bytes)
    return TargetModel(config, binding, base.documents if documents is None else documents, **options)


class Storage:
    """Observe a real adapter call and optionally actual writes in an owned tempdir.

    Not crash-safe, not authenticated, no production fsync or recovery claims.
    Tests prove handoff, no-write dry-run, receipt binding and readback only.
    """
    def __init__(self, current, directory=None):
        self.current = current
        self.directory = directory
        self.events = []
        self.requests = []
        if directory is not None:
            for p,b in current.source_files.items():
                target = directory / p; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(b)

    @contextmanager
    def transaction(self, request):
        self.events.append('enter')
        try:
            yield self
        finally:
            self.events.append('exit')

    def read_model(self):
        self.events.append('read')
        if self.directory is not None:
            self.current = rebuild(self.current, documents=tuple(
                ModelDocument(d.path,(self.directory/d.path).read_bytes()) for d in self.current.documents))
        return self.current

    def publish(self, request):
        self.events.append('publish'); self.requests.append(request)
        documents = {d.path:d for d in self.current.documents}
        documents.update({d.path:d for d in request.documents})
        if self.directory is not None:
            for d in request.documents:
                target=self.directory/d.path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(d.content)
        self.current=rebuild(self.current,documents=tuple(documents.values()))
        d=request.data
        return PublicationReceipt(request.sha256, d['target_root_sha256'], d['request_id'],
                                  tuple(d['changed_paths']), 'receipt-test')

    @property
    def backend(self): return ChangeBackend('test-storage','1',self.transaction)
