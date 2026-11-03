"""Inert native-shaped envelopes with independently sized decoded JSON bytes."""
import base64
from hashlib import sha256
import json
from zipfile import ZipFile
import zlib
from codex_control_tests.apply_reconcile_support import ReconcileCore

BINDING = {'repo_id':'12345678-1234-4234-8234-1234567890ab', 'base_commit':'a'*40,
           'fingerprint_algorithm':'patchharbor-state-v1', 'state_fingerprint':'b'*16}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',',':'), ensure_ascii=True).encode()


def sized_plan(size):
    empty = sha256(b'').hexdigest()
    stage = {'commit_id':'size.W', 'message':'Inert size boundary', 'role':'implementation',
        'before':{}, 'after':{'src/a.bin':empty, 'src/b.bin':empty},
        'payloads':{'src/a.bin':'', 'src/b.bin':''}, 'source_sha256':'e'*64,
        'test_plan':{'format_version':1, 'commit_id':'size.W', 'test_ids':[],
                     'test_files':['tests/test_example.py'], 'reason':'Synthetic byte boundary'}}
    value = {'format_version':2, 'handoff_kind':'patch_ready', 'bundle_number':'561',
        'source_result_sha256':'c'*64, 'binding':BINDING, 'apply_repository':'/tmp/owned-project',
        'branch':'dev', 'initial_dirty':False, 'stages':[stage], 'correction_of':None}
    base = len(encoded(value)); assert size >= base
    blocks, padding = divmod(size-base, 8)
    # Two equal original-byte payloads, each below the unchanged 32-MiB file cap.
    # eHh4 is the independent Base64 encoding of three literal x bytes.
    payload = 'eHh4'*blocks
    byte_count = blocks*3; h = sha256(); block = b'x'*65536
    for _ in range(byte_count//len(block)): h.update(block)
    h.update(block[:byte_count%len(block)])
    stage['payloads'] = {'src/a.bin':payload, 'src/b.bin':payload}
    stage['after'] = {'src/a.bin':h.hexdigest(), 'src/b.bin':h.hexdigest()}
    stage['message'] += 'p'*padding
    raw = encoded(value); assert len(raw) == size
    return raw, stage['after']


def write_stream(path, compressed):
    literal = repr(base64.b64encode(compressed).decode())
    script = ("#!/bin/sh\npython3 - <<'SPECROAD_APPLY_COMMIT_PLAN'\nimport json, zlib, base64\n"
              'DATA = json.loads(zlib.decompress(base64.b64decode('+literal+')))\n'
              '\nSPECROAD_APPLY_COMMIT_PLAN\n')
    with ZipFile(path,'w') as archive:
        archive.writestr('patch.json',encoded({'marker':'patch-harbor','format_version':1,
                                             'entrypoint':'run.sh',**BINDING}))
        archive.writestr('run.sh',script)
        archive.writestr('PATCHHARBOR_META/environment.json','{}')
        archive.writestr('PATCHHARBOR_META/CHAT_INSTRUCTIONS.md','Synthetic proof only.')
    return ReconcileCore().patch(path)


def sized_package(path, size):
    raw, expected = sized_plan(size)
    return write_stream(path,zlib.compress(raw)), expected
