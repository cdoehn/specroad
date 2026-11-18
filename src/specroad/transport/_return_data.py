"""Closed passive return inventory, reconstructed by the native Proposal fold."""
from hashlib import sha256

from ..model.canonical import canonical_json_bytes
from ..proposals.context import ProposalContext, reconstruct_proposal_target, specification_manifest
from ..proposals.validation import validate_proposal
from ._files import require

FORMAT = 'specroad-proposal-return-v1'
ENTRYPOINT = b"""#!/bin/bash
# PATCHHARBOR
set -euo pipefail
: "${SPECROAD_RETURN_PYTHON:?explicit local receiver required}"
exec "$SPECROAD_RETURN_PYTHON" -I -S -B - <<'SPECROAD_RETURN_CLIENT'
import json, os, socket
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as channel:
    channel.settimeout(float(os.environ['SPECROAD_RETURN_TIMEOUT']))
    channel.connect('\\0' + os.environ['SPECROAD_RETURN_SOCKET'])
    channel.sendall(json.dumps({'token': os.environ['SPECROAD_RETURN_TOKEN']}).encode() + b'\\n')
    data = bytearray()
    while not data.endswith(b'\\n'):
        part = channel.recv(1024)
        if not part or len(data) + len(part) > 65536:
            raise RuntimeError('invalid local receiver response')
        data.extend(part)
    result = json.loads(data)
    if result != {'status': 'proposal_received'}:
        raise RuntimeError('local proposal receipt failed')
    print('proposal_received')
SPECROAD_RETURN_CLIENT
"""


class ReturnData:
    """One complete native intent; neither a review nor write authority."""
    def __init__(self, container, original, basis):
        require(original.binding.proposal_id not in {a['id'] for a in basis.artifacts},
                'return_existing_proposal_identity', 6)
        value = original.data
        require(bool(value['change_plan']['request_id']), 'return_request_id_required', 2)
        require(not value['relations'] and not value['extensions'], 'return_initial_draft_content_required', 3)
        context = ProposalContext(original, basis)
        validate_proposal(context)
        target = reconstruct_proposal_target(context)
        before, after = basis.source_files, target.source_files
        delta, objects = [], {}
        for name in sorted(before.keys() | after.keys()):
            old, new = before.get(name), after.get(name)
            if old == new:
                continue
            digest = None if new is None else sha256(new).hexdigest()
            delta.append({'path': name, 'before_sha256': None if old is None else sha256(old).hexdigest(),
                'after_sha256': digest, 'size': None if new is None else len(new)})
            if new is not None:
                objects['data/' + digest] = new
        outbound = container.manifest
        reference = {k: v for k, v in outbound['reference'].items() if k != 'path'}
        manifest = {'format_version': FORMAT, 'outbound_sha256': container.sha256,
            'outbound_package_id': outbound['package_id'], 'reference': reference,
            'project_id': outbound['project_id'], 'project_path': outbound['project_path'],
            'proposal': {'path': original.path, 'sha256': original.sha256, 'binding': original.binding.data},
            'target_model_root_sha256': specification_manifest(target).sha256,
            'entrypoint_sha256': sha256(ENTRYPOINT).hexdigest(), 'delta': delta}
        manifest['return_id'] = sha256(FORMAT.encode() + b'\0' + canonical_json_bytes(manifest)).hexdigest()
        self.manifest = manifest
        self.prefix = '.specroad-return/' + manifest['return_id']
        self.contents = {self.prefix + '/' + p: b for p, b in {
            'return.json': canonical_json_bytes(manifest), 'proposal.json': original.source_bytes,
            'receive.sh': ENTRYPOINT, **objects}.items()}
        self.original, self.basis, self.target = original, basis, target
        self.entrypoint = self.prefix + '/receive.sh'
        self.no_changes = not delta

    def check_inspection(self, inspection):
        require(inspection.entrypoint == self.entrypoint, 'return_entrypoint_mismatch')
        fields = self.manifest['reference']
        require(all(str(getattr(inspection.manifest, key)) == fields[key]
                    for key in ('repo_id', 'base_commit', 'fingerprint_algorithm', 'state_fingerprint')),
                'return_native_binding_mismatch', 6)
        # Native inspection has already validated its separate passive handoff.
        entries = {e.path: e for e in inspection.entries
                   if e.role.value not in ('manifest', 'handoff')}
        require(set(entries) == set(self.contents), 'return_payload_inventory')
        for path, raw in self.contents.items():
            item = entries[path]
            mode = 0o755 if path == self.entrypoint else 0o644
            require(item.size == len(raw) and item.sha256 == sha256(raw).hexdigest()
                    and item.unix_mode == mode, 'return_payload_bytes_or_mode')
