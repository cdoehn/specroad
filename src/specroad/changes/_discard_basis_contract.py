"""Persistent inputs for independent discard-basis reconstruction, never a plan.

Selection is explicit; hashes and semantic resources are rebuilt from current
project bytes. Old journals remain readable without claiming restart support.
"""
from base64 import b64decode, b64encode
from binascii import Error as Base64Error
from hashlib import sha256

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
    return {'format_version': 'discard-basis-v2',
            'profile_chain': list(model.profile.profile_chain),
            'attachments': [a.data for a in sorted(model.attachment_descriptors, key=lambda a: a.path)],
            'language_package_paths': packages,
            'staging_images': [{'path': d.path, 'bytes_base64': b64encode(d.content).decode('ascii')}
                               for d in sorted(preflight.request.documents, key=lambda d: d.path)]}


def validate_discard_basis(value):
    """Closed passive selection contract; no filesystem or authorization calls."""
    fields = {'format_version', 'profile_chain', 'attachments', 'language_package_paths'}
    if (type(value) is not dict
            or (value.get('format_version'), set(value)) not in (
                ('discard-basis-v1', fields), ('discard-basis-v2', fields | {'staging_images'}))):
        raise JournalError('invalid_discard_basis')
    if 'staging_images' in value:
        staging_images(value)
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


def staging_images(selection):
    """Decode canonical, explicitly bound expected bytes, never a saved plan."""
    values = selection.get('staging_images')
    if type(values) is not list:
        raise JournalError('invalid_discard_staging_images')
    images = {}
    for item in values:
        if type(item) is not dict or set(item) != {'path', 'bytes_base64'}:
            raise JournalError('invalid_discard_staging_images')
        path = project_path(item['path'])
        text = item['bytes_base64']
        try:
            raw = b64decode(text, validate=True)
        except (ValueError, TypeError, Base64Error) as error:
            raise JournalError('invalid_discard_staging_images') from error
        if (type(text) is not str or b64encode(raw).decode('ascii') != text
                or path in images):
            raise JournalError('invalid_discard_staging_images')
        images[path] = raw
    if list(images) != sorted(images):
        raise JournalError('invalid_discard_staging_images')
    return images


def verify_staging_bindings(value):
    selection = value.get('discard_basis', {})
    if selection.get('format_version') != 'discard-basis-v2':
        return
    images = staging_images(selection)
    if set(images) != {entry['path'] for entry in value['files']}:
        raise JournalError('discard_staging_inventory_mismatch')
    for entry in value['files']:
        raw = images[entry['path']]
        if len(raw) != entry['after_size'] or sha256(raw).hexdigest() != entry['after_sha256']:
            raise JournalError('discard_staging_binding_mismatch')


def match_basis_version(expected, actual):
    """Compare old journals against the independently regenerated old contract."""
    selection = actual.get('discard_basis')
    if selection is None:
        expected.pop('discard_basis')
    elif selection['format_version'] == 'discard-basis-v1':
        expected['discard_basis'].pop('staging_images')
        expected['discard_basis']['format_version'] = 'discard-basis-v1'
