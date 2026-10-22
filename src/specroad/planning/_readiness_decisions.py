"""Internal gate contributions sharing one owned Readiness input binding.

These values organize observations, not permissions. Only the final projection
turns the contributions into the existing public report shape.
"""
from dataclasses import dataclass, field
from typing import Literal

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..storage.json_syntax import parse_json_object

GATES = ('scope', 'approval', 'implementation', 'verification', 'coverage',
         'risks', 'issues', 'relations')
GateStatus = Literal['passed', 'failed', 'incomplete', 'not_applicable']


@dataclass(frozen=True)
class ReadinessBinding:
    _encoded: bytes

    @classmethod
    def from_value(cls, value):
        return cls(canonical_json_bytes(value))

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return canonical_json_sha256(self.data)


@dataclass(frozen=True)
class BlockerDecision:
    binding: ReadinessBinding
    _encoded: bytes

    @classmethod
    def from_observation(cls, binding: ReadinessBinding, observation: dict):
        # The native blocker assessment already binds this complete input.
        assert observation['input_sha256'] == binding.sha256
        return cls(binding, canonical_json_bytes(observation))

    @property
    def data(self):
        return parse_json_object(self._encoded)


@dataclass
class GateDecision:
    gate_id: str
    binding: ReadinessBinding
    subject_ids: list[str]
    status: GateStatus = 'passed'
    evidence_bindings: list[dict] = field(default_factory=list)
    findings: list[dict] = field(default_factory=list)

    def finding(self, subject, reason, *, status: GateStatus = 'incomplete', evidence_ids=(), relation_ids=()):
        self.findings.append({'gate_id': self.gate_id, 'subject_id': subject, 'reason': reason,
            'blocking': True, 'evidence_ids': sorted(set(evidence_ids)),
            'relation_ids': sorted(set(relation_ids))})
        if self.status != 'failed':
            self.status = status

    def include_blocker(self, decision: BlockerDecision):
        assert decision.binding is self.binding
        observation = decision.data
        self.evidence_bindings.append(observation)
        for reason in observation['reasons']:
            self.finding(observation['subject_id'], reason, status=observation['status'],
                evidence_ids=(() if observation['review_sha256'] is None else
                              (observation['review']['review_id'],)))

    def result(self, *, complete):
        status = self.status
        # Empty inventories waive no gate until native scope is complete.
        if not self.subject_ids and complete and not self.findings:
            status = 'not_applicable'
        unique = {canonical_json_bytes(f): f for f in self.findings}
        findings = sorted(unique.values(), key=lambda f:
            ((f['subject_id'] or '').encode('utf-8'), f['reason'].encode('utf-8'), canonical_json_bytes(f)))
        return {'gate_id': self.gate_id, 'status': status, 'subject_ids': self.subject_ids,
                'evidence_bindings': self.evidence_bindings, 'findings': findings}
