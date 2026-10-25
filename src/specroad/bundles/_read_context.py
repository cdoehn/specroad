"""Shared command eligibility and projections for an already verified partial.

This context neither loads nor authorizes a project. Callers keep their native
snapshot, model checks and currentness ordering; metadata/validation readers
retain their own result schemas instead of using the graph-read envelope.
"""
from dataclasses import dataclass


_READERS = frozenset(('artifact.show', 'query', 'trace', 'why', 'impact', 'diff',
    'render', 'document.render', 'view.render', 'diagram', 'bundle.verify', 'project.inspect',
    'environment.check', 'recover.status', 'lock.status'))


@dataclass(frozen=True)
class PartialReadContext:
    snapshot: object

    @staticmethod
    def allows(command, options):
        from ..cli.registry import EffectScope
        return command.effect_scope is EffectScope.NONE and (
            command.command_id in _READERS or
            (command.command_id == 'validate' and options.get('--partial') is True))

    @property
    def project(self):
        return dict(project_root=str(self.snapshot.boundary.root),
                    project_id=self.snapshot.configuration.project_id)

    @property
    def details(self):
        return self.snapshot.details

    def coverage(self, **extra):
        return dict(scope='partial_bundle_artifacts', source_count=len(self.snapshot.records),
            relation_count=sum(len(r.relations) for r in self.snapshot.records),
            observation_sha256=self.snapshot.observation_sha256,
            validation_scope='partial_payload_model', atomic_snapshot=False, **extra)

    def result(self, command, payload, details, *, diagnostics=(), project=None):
        """Project a successful graph read after the caller's final checks."""
        from ..cli.results import CommandResult, ResultStatus
        return CommandResult(command, status=ResultStatus.PARTIAL, partial_scope='partial_bundle_artifacts',
            result=payload, diagnostics=diagnostics,
            project=self.project if project is None else project, details=details)

    def finish(self, command, schema, payload, details, diagnostics=()):
        """Retain the query/document readers' freshness, schema and policy order."""
        from ..cli.result_schemas import validate_result_document
        from ..cli.results import CommandResult, FailureKind
        self.snapshot.verify_current()
        validate_result_document(schema, payload)
        project = self.project
        details = {**details, **self.details}
        if any(f.severity == 'error' for f in diagnostics):
            return CommandResult.failed(command, FailureKind.POLICY, complete=True, result=payload,
                diagnostics=diagnostics, project=project, details=details)
        return self.result(command, payload, details, diagnostics=diagnostics, project=project)
