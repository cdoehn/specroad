"""Owned raster bytes, closed render policies and effects; no output oracles."""
from base64 import b64decode
from hashlib import sha256
from dataclasses import FrozenInstanceError
import builtins
import io
import os

import pytest

from specroad.documents import RenderError, render_document
from specroad.documents._render_assets import (MAX_RENDER_ATTACHMENT_BYTES,
                                               resolve_render_attachment)
from specroad.model.attachments import AttachmentDescriptor
from specroad.model.errors import ModelError
from specroad.validation import ModelDocument
from support.read_only import no_write_attempts
from support.records import block_value, ref
from support.targets import model
from test_document_rendering_behavior import composed_values
from test_document_includes import include_project


PNG = b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aH1UAAAAASUVORK5CYII=')
PATH = 'attachments/owned.png'


def supplied_asset(raw=PNG, media_type='image/png', *, markdown=None):
    block = block_value('prose')
    block['payload']['markdown'] = markdown or '![owned](attachments/owned.png)'
    descriptor = AttachmentDescriptor(PATH, media_type, len(raw), sha256(raw).hexdigest())
    return model(composed_values(block), attachments=[descriptor],
                 resource_files=[ModelDocument(PATH, raw)])


def resolve(supplied):
    return resolve_render_attachment(supplied, PATH, source_path='source-block.json', error_type=RenderError)


def test_attachment_binding_owns_exact_supplied_bytes_and_not_a_path_to_open():
    supplied = supplied_asset()
    with no_write_attempts():
        attachment = resolve(supplied)
    assert attachment.path == PATH and attachment.media_type == 'image/png'
    assert attachment.content == PNG and attachment.sha256 == sha256(PNG).hexdigest()
    with pytest.raises(FrozenInstanceError):
        attachment.content = b'replaced'


@pytest.mark.parametrize(('media_type', 'signature'), [
    ('image/png', b'\x89PNG\r\n\x1a\n'), ('image/jpeg', b'\xff\xd8\xff'),
    ('image/gif', b'GIF87a'), ('image/gif', b'GIF89a'),
    ('image/webp', b'RIFF\x00\x00\x00\x00WEBP'),
])
def test_each_allowed_media_type_binds_bytes_without_decoding_or_extension_guessing(media_type, signature):
    # Synthetic signature fixtures establish admission, not valid image decoding.
    raw = signature + b'synthetic-admission-fixture'
    supplied = supplied_asset(raw, media_type)
    with no_write_attempts():
        attachment = resolve(supplied)
    assert attachment.media_type == media_type and attachment.content == raw
    assert attachment.sha256 == sha256(raw).hexdigest()


@pytest.mark.parametrize('media_type', ['image/svg+xml', 'text/html', 'application/pdf',
    'application/javascript', 'application/octet-stream', 'image/png; charset=utf-8',
    'IMAGE/PNG', 'https://invalid.test/image/png'])
def test_unsupported_or_active_media_cannot_select_a_renderer(media_type):
    supplied = supplied_asset(media_type=media_type)
    with no_write_attempts(), pytest.raises(RenderError) as caught:
        render_document(supplied, ref('DOC'), output_format='html')
    assert caught.value.diagnostic()['reason'] == 'render_attachment_media_provider_required'
    assert caught.value.pointer == '/payload/markdown'


@pytest.mark.parametrize('media_type', ['image/png', 'image/jpeg', 'image/gif', 'image/webp'])
def test_declared_raster_type_does_not_admit_html_bytes(media_type):
    supplied = supplied_asset(b'<svg onload="foreign()"></svg>', media_type)
    with no_write_attempts(), pytest.raises(RenderError) as caught:
        render_document(supplied, ref('DOC'), output_format='html')
    assert caught.value.diagnostic()['reason'] == 'render_attachment_signature_mismatch'


def test_oversized_attachment_is_rejected_without_truncation_or_external_loading():
    raw = PNG + b'0' * (MAX_RENDER_ATTACHMENT_BYTES - len(PNG) + 1)
    supplied = supplied_asset(raw)
    with no_write_attempts(), pytest.raises(RenderError) as caught:
        render_document(supplied, ref('DOC'))
    assert caught.value.diagnostic()['reason'] == 'render_attachment_size_limit'
    assert supplied.source_files[PATH] == raw


@pytest.mark.parametrize('output_format', ['markdown', 'html'])
@pytest.mark.parametrize('markdown', [
    '![owned](attachments/owned.png "Owned image")',
    '[**owned**](attachments/owned.png "Owned image")',
    '[![owned](attachments/owned.png)](attachments/owned.png)',
    '![first](attachments/owned.png) ![second](attachments/owned.png)',
])
def test_embedding_cannot_read_files_write_start_processes_or_access_network(monkeypatch, output_format, markdown):
    supplied = supplied_asset(markdown=markdown)
    before = supplied.source_files
    calls = []
    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError('A byte-owned renderer attempted file access')
    with no_write_attempts(), monkeypatch.context() as guards:
        for owner, name in ((builtins, 'open'), (io, 'open'), (os, 'open')):
            guards.setattr(owner, name, forbidden)
        render_document(supplied, ref('DOC'), output_format=output_format)
    assert not calls and supplied.source_files == before


@pytest.mark.parametrize('output_format', ['markdown', 'html'])
def test_the_same_included_attachment_can_be_used_without_copying_or_mutating_records(output_format):
    values = include_project()
    values[-1]['payload']['markdown'] = '![owned](attachments/owned.png)'
    descriptor = AttachmentDescriptor(PATH, 'image/png', len(PNG), sha256(PNG).hexdigest())
    supplied = model(values, attachments=[descriptor], resource_files=[ModelDocument(PATH, PNG)])
    before = supplied.source_files
    with no_write_attempts():
        render_document(supplied, ref('DOC'), output_format=output_format)
    assert supplied.source_files == before


@pytest.mark.parametrize('output_format', ['markdown', 'html'])
def test_explicit_matching_format_policy_is_passive_and_preserves_sources(output_format):
    values = composed_values(block_value('prose'))
    values[0]['render_policy'] = {'formats': [output_format]}
    supplied = model(values)
    before = supplied.source_files
    with no_write_attempts():
        render_document(supplied, ref('DOC'), output_format=output_format)
    assert supplied.source_files == before


@pytest.mark.parametrize('formats', [None, [], 'html', ['html', 'html'], ['html', 1],
                                    [['html']], ['csv'], ['json']])
def test_malformed_policy_is_rejected_before_presentation(formats):
    values = composed_values(block_value('prose'))
    values[0]['render_policy'] = {'formats': formats}
    supplied = model(values)
    with no_write_attempts(), pytest.raises(RenderError) as caught:
        render_document(supplied, ref('DOC'))
    assert caught.value.diagnostic()['reason'] == 'render_policy_formats_invalid'
    assert caught.value.pointer == '/render_policy/formats'


@pytest.mark.parametrize('output_format', ['markdown', 'html'])
def test_included_document_cannot_bypass_its_format_policy(output_format):
    values = include_project()
    values[1]['render_policy'] = {'formats': ['html' if output_format == 'markdown' else 'markdown']}
    supplied = model(values)
    with no_write_attempts(), pytest.raises(RenderError) as caught:
        render_document(supplied, ref('DOC'), output_format=output_format)
    assert caught.value.diagnostic()['reason'] == 'render_document_format_not_declared'
    assert caught.value.path.endswith('/' + ref('DOC', '1') + '.json')


def test_an_unknown_policy_key_cannot_hide_behind_a_valid_formats_list():
    values = composed_values(block_value('prose'))
    values[0]['render_policy'] = {'formats': ['html'], 'template': 'arbitrary-command'}
    supplied = model(values)
    with no_write_attempts(), pytest.raises(RenderError) as caught:
        render_document(supplied, ref('DOC'), output_format='html')
    assert caught.value.diagnostic()['reason'] == 'render_policy_provider_required'


def test_replaced_owned_attachment_bytes_are_not_rendered_from_a_stale_handle():
    supplied = supplied_asset()
    resource = next(item for item in supplied.resource_files if item.path == PATH)
    object.__setattr__(resource, 'content', b'replaced')
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        render_document(supplied, ref('DOC'))
    assert caught.value.diagnostic()['reason'] == 'target_sources_changed'
