"""Owned XML with namespace-sensitive passive data and real JSON targets."""
import base64
import json
from hashlib import sha256

from .reqif_objects import document

CONTEXT = {'source_system': 'vendor Ω', 'source_document': 'explicit:document', 'external_revision': None}


def opaque_source(text='日本語 e\u0301 é 😀'):
    raw = document(extensions='<TOOL-EXTENSIONS xmlns:v="urn:vendor/a" v:type="v:Custom">'
        'before<v:part v:flag="true">' + text + '<v:child/>after</v:part>tail</TOOL-EXTENSIONS>')
    return raw.replace(b'xml:lang="de"', b'xml:lang="de" xmlns:v="urn:vendor/a" v:flag="original"')


def source_entry(raw, context=None):
    return {**(CONTEXT if context is None else context), 'source_sha256': sha256(raw).hexdigest(),
            'source_size': len(raw), 'source_base64': base64.b64encode(raw).decode('ascii')}


def source_key(raw, context=None):
    c = CONTEXT if context is None else context
    return [c['source_system'], c['source_document'], c['external_revision'], sha256(raw).hexdigest()]


def target_bytes(*entries):
    return json.dumps({'extensions': {'specroad.reqif': {
        'format_version': 'reqif-preservation-v1', 'sources': list(entries)}}}, ensure_ascii=False).encode()
