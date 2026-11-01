"""Authorize public SafeExportPlan fields; never construct or persist the plan."""
import os
from pathlib import Path

from ._contract import valid_digest
from ._files import directory, overlap, require


BINDING_FIELDS = ('repo_id', 'base_commit', 'state_fingerprint', 'fingerprint_algorithm')


def binding(context):
    return {name: str(getattr(context, name)) for name in BINDING_FIELDS}


def repository_root(context):
    return Path(str(context.repository_path))


def pre_bootstrap_output(output_root):
    """Refuse obvious protected output namespaces before extracting code.

    This does not discover or select the source repository. Only the public
    safe context may supply that identity; registry-wide checks follow loading.
    """
    home = os.environ.get('HOME')
    require(bool(home) and Path(home).is_absolute(), 'transport_home_required', 2)
    for variable, default in (('XDG_CONFIG_HOME', '.config'), ('XDG_STATE_HOME', '.local/state')):
        root = Path(os.environ.get(variable, str(Path(home) / default))) / 'patchharbor'
        require(root.is_absolute() and not overlap(output_root, root), 'transport_output_overlaps_protected_state')


def authorize(api, context, plan, *, project_root, output_root):
    repo = repository_root(context)
    require(project_root == repo or repo in project_root.parents, 'transport_project_outside_repository')
    require(plan.context == context and type(context.dirty) is bool,
            'transport_plan_context_changed', 6)
    require(plan.maintenance_enabled is False and valid_digest(plan.binding_sha256),
            'unsafe_transport_export_plan')
    require(plan.output_directory == output_root and plan.diagnostics_parent == output_root,
            'transport_output_boundary_changed', 6)
    # This is the pinned Linux host's documented XDG operating namespace, not
    # a private PH API or a read/write of its registry/configuration format.
    home = os.environ.get('HOME')
    require(bool(home) and Path(home).is_absolute(), 'transport_home_required', 2)
    config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path(home) / '.config'))) / 'patchharbor'
    state = Path(os.environ.get('XDG_STATE_HOME', str(Path(home) / '.local/state'))) / 'patchharbor'
    locks = directory(state / 'locks', owned=True).root
    expected_locks = (locks / 'registry.lock', locks / ('repository-' + str(context.repo_id) + '.lock'))
    require(plan.lock_paths == expected_locks, 'transport_lock_boundary_invalid')
    directory(config, owned=True)
    directory(output_root, owned=True)
    registered = api.repositories().repositories
    require(any(str(item.repo_id) == str(context.repo_id)
                and Path(str(item.repository_path)) == repo and item.status.value == 'ok'
                for item in registered), 'transport_registration_changed', 6)
    for item in registered:
        other = Path(str(item.repository_path))
        require(not overlap(output_root, other) and not overlap(locks, other),
                'transport_output_overlaps_repository')
    for protected in (project_root, repo, config, state):
        require(not overlap(output_root, protected), 'transport_output_overlaps_protected_state')
    configuration = api.configuration(repo)
    require(configuration.exchange_directory == plan.configured_exchange,
            'transport_exchange_changed', 6)
    return {'repository_root': str(repo), 'source_binding': binding(context),
        'dirty': context.dirty, 'output_directory': str(output_root),
        'diagnostics_parent': str(plan.diagnostics_parent),
        'lock_paths': [str(p) for p in plan.lock_paths],
        'configured_exchange': None if plan.configured_exchange is None else str(plan.configured_exchange),
        'maintenance_enabled': False, 'binding_sha256': plan.binding_sha256,
        'registration_performed': False, 'recovery_performed': False,
        'archive_performed': False, 'apply_started': False}
