"""Persistent inputs for independent discard-basis reconstruction, never a plan.

Selection is explicit; hashes and semantic resources are rebuilt from current
project bytes. Old journals remain readable without claiming restart support.
"""
from ..model.attachments import AttachmentDescriptor
from ..model.paths import project_path
from ..profiles._contract import parse_profile_key
from .journal_values import JournalError


def discard_basis_descriptor(preflight):
    model = preflight._model
    available = list(preflight._package_files)
    packages = []
    for package in model.language_packages:
        match = next((d for d in available if d.content == package.source_bytes), None)
        if match is None:
            raise JournalError('discard_basis_package_unbound', exit_code=6)
        available.remove(match)
        packages.append(match.path)
    if available:
        raise JournalError('discard_basis_package_unbound', exit_code=6)
    return {'format_version': 'discard-basis-v1',
            'profile_chain': list(model.profile.profile_chain),
            'attachments': [a.data for a in sorted(model.attachment_descriptors, key=lambda a: a.path)],
            'language_package_paths': packages}


def validate_discard_basis(value):
    """Closed passive selection contract; no filesystem or authorization calls."""
    fields = {'format_version', 'profile_chain', 'attachments', 'language_package_paths'}
    if (type(value) is not dict or set(value) != fields
            or value['format_version'] != 'discard-basis-v1'):
        raise JournalError('invalid_discard_basis')
    chain = value['profile_chain']
    if type(chain) is not list or not chain:
        raise JournalError('invalid_discard_basis_profiles')
    identities = [parse_profile_key(key)[0] for key in chain]
    if identities[0] != 'core' or len(set(identities)) != len(identities):
        raise JournalError('invalid_discard_basis_profiles')
    attachments = value['attachments']
    if type(attachments) is not list:
        raise JournalError('invalid_discard_basis_attachments')
    paths = [AttachmentDescriptor.from_data(item).path for item in attachments]
    if (paths != sorted(paths) or len(set(p.casefold() for p in paths)) != len(paths)
            or any(not p.startswith('attachments/') for p in paths)):
        raise JournalError('invalid_discard_basis_attachments')
    packages = value['language_package_paths']
    if type(packages) is not list:
        raise JournalError('invalid_discard_basis_packages')
    names = [project_path(path) for path in packages]
    if (len(set(p.casefold() for p in names)) != len(names)
            or any(p.split('/')[0] not in ('profiles', 'rules') or not p.endswith('.json')
                   or any(part.casefold() == '.specroad' for part in p.split('/')) for p in names)):
        raise JournalError('invalid_discard_basis_packages')
