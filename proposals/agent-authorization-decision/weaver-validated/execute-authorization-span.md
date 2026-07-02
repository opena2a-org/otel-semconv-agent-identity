# Execute Authorization Span

## Required

| Attribute | Supporting Libraries |
| --- | --- |
| gen_ai.agent.authorization.outcome | [agent-authorization-decision] |
| gen_ai.operation.name | [agent-authorization-decision] |

## Conditionally Required

| Attribute | Supporting Libraries |
| --- | --- |
| gen_ai.agent.authorization.reason | [agent-authorization-decision] |

## Recommended

| Attribute | Supporting Libraries |
| --- | --- |
| gen_ai.agent.authorization.policy | [agent-authorization-decision] |
| gen_ai.agent.capability | [agent-authorization-decision] |
| gen_ai.agent.drift.method | [agent-authorization-decision] |
| gen_ai.agent.scan.method | [agent-authorization-decision] |
| gen_ai.agent.trust.method | [agent-authorization-decision] |

## Opt-In

| Attribute | Supporting Libraries |
| --- | --- |
| gen_ai.agent.drift.score | [agent-authorization-decision] |
| gen_ai.agent.public_key.algorithm | [agent-authorization-decision] |
| gen_ai.agent.scan.verdict | [agent-authorization-decision] |
| gen_ai.agent.trust.score | [agent-authorization-decision] |

[agent-authorization-decision]: ../scenarios/agent-authorization-decision/scenario.py
