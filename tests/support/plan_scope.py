"""Synthetic protocol payload paths, independent of the repository's documents."""
from hashlib import sha256
import base64

PLAN_PARTS = (
    'docs/implementation/milestones/M01.md',
    'docs/implementation/milestones/M20.md',
    'docs/implementation/supplements/1-a.md',
    'docs/implementation/supplements/20-z.md',
    'docs/implementation/decisions/example-17.md',
    'docs/implementation/matrices/Requirements.md',
    'docs/implementation/matrices/Verifikation.md',
    'docs/implementation/matrices/Szenarien.md',
    'docs/implementation/matrices/Regressionen.md',
    'docs/implementation/matrices/Uebergabe.md',
    'docs/implementation/rules/Grundlagen.md',
    'docs/implementation/rules/C_Abnahme.md',
    'docs/implementation/audit/Audit_Nacharbeiten.md',
)
OUTSIDE_PLAN = (
    'src/example.py', 'tests/test_example.py',
    'docs/AGENTS.md', 'docs/implementation/AGENTS.md',
    'docs/implementation/decisions/AGENTS.md',
    'docs/development/Plan_Arbeitsregeln.md', 'DEVELOPMENT.md',
    'docs/implementation/history/decision.md',
    'docs/implementation/milestones/M00.md',
    'docs/implementation/milestones/M21.md',
    'docs/implementation/milestones/M1.md',
    'docs/implementation/supplements/0-a.md',
    'docs/implementation/supplements/21-a.md',
    'docs/implementation/decisions/example.py',
    'docs/implementation/decisions/sub/example.md',
    'docs/implementation/decisions/../AGENTS.md',
    'docs/implementation/decisions/.hidden.md',
    'docs/implementation/matrices/Other.md',
    'docs/implementation/rules/Other.md',
    'docs/implementation/audit/Other.md',
    'docs/implementation/decisions/example.md/extra',
    'docs/implementation/decisions/example.md\n',
    '/docs/implementation/decisions/example.md',
    'docs\\implementation\\decisions\\example.md',
)


def add_plan_payload(stage, name, raw=b'Synthetic normative plan acceptance\n'):
    stage['after'][name] = sha256(raw).hexdigest()
    stage['payloads'][name] = base64.b64encode(raw).decode()
