"""Production gates for a compiled authoring target, using native specialists."""
from ..validation import ModelGate
from ..validation.values import HOOK_NAMES
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from ..qualification.project import validate_project
from ..qualification.services import native_services


def publication_gates(sources, target, *, services=None, transaction_id=None, request_id=None):
    services = native_services(services)
    expected = {v['id']: v for v in target.artifacts}
    files = {**target.source_files, **{p: sources.snapshot.raw[p] for p in sources.packages}}
    def dependencies(context):
        return context.dependency_result({i: list(context.all_ids) for i in context.subjects})
    def check(context):
        if ({i: context.artifact(i) for i in context.all_ids} != expected
                or {d.path: d.content for d in context.documents} !=
                    {d.path: d.content for d in target.documents}):
            raise ModelError('authoring_target_binding_changed')
        sources.verify_history(transaction_id=transaction_id, request_id=request_id,
            new_archives={p:b for p,b in target.source_files.items() if p.startswith('archive/objects/') and p not in sources.archives})
        # Real whole-target validators reobserve external inputs on every call.
        # Old receipt lineage was verified against the original source. It is
        # not misrepresented as a receipt for this still-unpublished target.
        validate_project(files, services=services)
        return context.result()
    return tuple(ModelGate(name, 'native-authoring-project-v1', dependencies, check,
        canonical_json_sha256({'before': sources.model._sources_sha256,
                              'after': target._sources_sha256})) for name in (
        *(n for n in HOOK_NAMES if n not in ('profile_lint', 'language_policy')),
        'extension:plan-authoring', 'extension:target-resources'))
