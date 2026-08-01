---
name: rpacore-automation-development
description: Develop RPA Core Skills and Transactions with supported public APIs. Use for skill wiring, ProcessContext state/resources, configuration, failures, retries, artifacts, or idempotent effects.
---

# Develop an RPA Core automation

Before changing code, run `rpacore version` and confirm it satisfies the Core
range in the repository's [`manifest.toml`](../../manifest.toml). Stop on a
mismatch.

Use the public
[API reference](https://github.com/renatomoselli/rpacore/blob/0a50fcfa31692232b4fe8807997ce026c1e26bf3/docs/api.md),
[configuration reference](https://github.com/renatomoselli/rpacore/blob/0a50fcfa31692232b4fe8807997ce026c1e26bf3/docs/config.md),
and
[security guidance](https://github.com/renatomoselli/rpacore/blob/0a50fcfa31692232b4fe8807997ce026c1e26bf3/docs/security.md)
for detailed signatures and behavior.

## Workflow

1. Import supported APIs from top-level `rpacore`.
2. Implement cohesive `Skill.execute(ctx)` units and wire explicit order in a
   `Transaction` with a stable application-owned `definition_identity`.
3. Keep JSON-safe recovery data in `ctx.state`; keep live handles in
   `ctx.resources` and close them explicitly.
4. Validate configuration before filesystem, database, queue, or network
   mutation.
5. Preserve `BusinessException` versus technical/system failure and bound
   retries.
6. Make retryable external effects idempotent and test their failure path.

Never catch a failure merely to report success. Keep credentials and
unnecessary sensitive data out of state, logs, artifacts, reports, and
exception messages.
