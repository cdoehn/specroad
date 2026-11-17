"""An additional checked-Work prerequisite, never a substitute for live reviews."""
from ..qualification.errors import guarded, persisted_contract
from ..work._public_errors import work_errors
from ..work.open_existing import open_existing_work
from ..work.proposal import proposal_work_result, checked
from .scope import specification_manifest
from .values import require


@guarded
@persisted_contract
@work_errors
def check_work_handoff(path, snapshot, original, services):
    from ..cli.commands import builtin_registry
    store = open_existing_work(path, registry=builtin_registry())
    descriptor, _, _, _, _ = checked(store.read())
    require(descriptor['project_id'] == snapshot.model.configuration.project_id
        and descriptor['basis_sha256'] == specification_manifest(snapshot.model).sha256
        and descriptor['binding'] == original.binding.data,
            'proposal_work_live_binding_changed', exit_code=6)
    report, code = proposal_work_result(store, services=services)
    require(code == 0 and report['passed'] and report['full_semantic_validation'],
            'proposal_work_check_not_passed', exit_code=6)
