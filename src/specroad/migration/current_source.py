"""Native 0.2 backup qualification; historical readers retain their own domains."""
from dataclasses import dataclass
from ..model.canonical import canonical_json_sha256 as digest
from ..storage.json_syntax import parse_json_object
from .plan_values import require, file_bindings


@dataclass(frozen=True)
class CurrentSource:
    project_id: str
    model_root_sha256: str

    @property
    def data(self):
        return {'project_id': self.project_id}

    @property
    def source_contract(self):
        from .additive import source_contract
        return {'contract_id': 'specroad-current-project', 'contract_version': '1.0.0', **source_contract()}


def inventory_bytes(files):
    from ..qualification.project import project_bytes
    require(parse_json_object(files['specroad.json']).get('schema_version') == '0.2.0',
            'migration_source_version_mismatch')
    model, root = project_bytes(project_files(files))
    return CurrentSource(model.configuration.project_id, root)


def preservation_history(files):
    """Revalidate original domains without promoting history to current evidence."""
    from ..qualification.project import project_bytes
    model, _ = project_bytes(project_files(files))
    historical = None
    if model.legacy_manifest is not None:
        from .history import verify_migrated_history
        historical = verify_migrated_history(files, project_id=model.configuration.project_id).data['historical']
    protected = file_bindings({p: b for p, b in files.items() if p != 'specroad.json'})
    return {'historical': {'legacy': historical, 'preserved_files_sha256': digest(protected)},
            'current_context_verified': False, 'external_run_verified': False, 'approval_granted': False}


def project_files(files):
    """Separate one known passive init original from the native model input.

    Preserve it in the complete migration/backup byte inventory. Its original
    inode metadata and prepared state are not current filesystem or completion
    evidence; source admission and writes still require live native preflight.
    Unknown/active operational paths continue through the existing fail-closed
    qualifier. Nothing here grants approval or repairs an interrupted root.
    """
    from hashlib import sha256
    from ..authoring._bootstrap_io import COMPLETED
    from ..authoring._bootstrap_record import record_values
    from ..authoring._initial_content import distribution_content
    prefix = '/'.join(COMPLETED) + '/'
    retained = {p: raw for p, raw in files.items() if p.startswith(prefix)}
    if not retained:
        return dict(files)
    path = prefix + 'journal.json'
    require(set(retained) == {path}, 'migration_bootstrap_original_inventory')
    raw = retained[path]
    require(type(raw) is bytes and len(raw) <= 262144, 'migration_bootstrap_original_size')
    resources = distribution_content()[3]
    value, _ = record_values(raw, resources)
    # Pinned release resources have independent original hashes. Dynamic IDs,
    # config/document hashes and inode values stay historical, not synthesized.
    require(all(value['entries'][p]['size'] == len(content)
                and value['entries'][p]['sha256'] == sha256(content).hexdigest()
                for p, content in resources.items()), 'migration_bootstrap_resource_binding')
    return {p: raw for p, raw in files.items() if p not in retained}
