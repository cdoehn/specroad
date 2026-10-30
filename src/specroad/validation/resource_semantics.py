"""Native normative resource readers, independent of an import or writer.

Schema/hash projections alone do not check a resource's content or bindings.
Only implemented versioned readers are selected here; resource data never
registers a validator, executes code or supplies a successful gate callback.
"""
from ..model.errors import ModelError
from ..model.paths import PathClass, classify_path
from ..storage.json_syntax import parse_json_object


def check_normative_resources(model):
    from ..mappings import ExchangeMapping, ExternalIdentityRegistry, select_mapping, select_registries
    from ..mappings.csv_profile import CSVProfile
    from ..exchange.csv import select_csv_profile
    readers = {'exchange-mapping-v1': ExchangeMapping,
               'external-identity-registry-v1': ExternalIdentityRegistry,
               'csv-profile-v1': CSVProfile}
    mappings, registries, profiles = [], [], []
    for document in model.resource_files:
        kind = classify_path(document.path, model.configuration)
        if kind is PathClass.RULE:
            # Profile rules already use the closed ProfileResource/SRX contract.
            # A standalone rule needs its own implemented native format; a file
            # with only rule_id/version/hash cannot masquerade as such a rule.
            raise ModelError('standalone_rule_reader_required', path=document.path)
        if kind is not PathClass.MAPPING:
            continue
        value = parse_json_object(document.content)
        reader = readers.get(value.get('mapping_format_version'))
        if reader is None:
            raise ModelError('mapping_native_reader_required', path=document.path)
        resource = reader(document.content)
        (mappings if reader is ExchangeMapping else registries if reader is ExternalIdentityRegistry
         else profiles).append(resource)
    for mapping in mappings:
        select_mapping(mappings, key=mapping.key, expected_sha256=mapping.sha256)
    select_registries(registries, bindings=[r.binding() for r in registries], mappings=mappings)
    for profile in profiles:
        select_csv_profile([*mappings, *registries, *profiles], key=profile.key, expected_sha256=profile.sha256)
