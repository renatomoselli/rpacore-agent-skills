---
name: rpacore-automation-development
description: Design and implement RPA Core automations, or adopt Core in an existing Python script. Use for transaction boundaries, Step wiring, durable state, resources, failure policy, and replayable effects.
---

# Develop an RPA Core automation

Run the project's `rpacore version` and compare it with the exact supported
version in [`manifest.toml`](../../manifest.toml). Stop on a mismatch or a
missing manifest; do not guess compatibility from a skill copied on its own.

Use the [API reference](https://github.com/renatomoselli/rpacore/blob/493252649ee6b9d387008e6b7ed41908e2733f46/docs/api.md),
[configuration reference](https://github.com/renatomoselli/rpacore/blob/493252649ee6b9d387008e6b7ed41908e2733f46/docs/config.md), and
[security guidance](https://github.com/renatomoselli/rpacore/blob/493252649ee6b9d387008e6b7ed41908e2733f46/docs/security.md) for exact contracts.

## Design from a business process

For a new workflow, identify the unit of work, input identity, expected output,
and evidence of completion. Keep the design proportional to the request.

- Choose step boundaries around recoverable work and external effects.
- Select ordinary Engine execution for explicitly non-durable work,
  execute_transaction with a database for durable one-off execution, or
  run_queue_loop when delivery/claim ownership is required.
- Identify JSON-safe replay inputs, runtime-only clients, business rejections,
  technical failures, and which effects can be verified after interruption.
- State unresolved business rules before encoding guesses as successful work.

## Adopt Core in an existing script

Inventory observable behavior and side effects before restructuring. Capture
representative outputs and failure cases with local fixtures or controlled
clients. Extract one bounded Step/Transaction while retaining existing domain
libraries, then verify parity before introducing durable execution.

Choose application-owned definition identity and replay behavior explicitly.
A script with an unverifiable effect needs a stated reconciliation limitation;
adding checkpoints alone does not make it safe to retry. Preserve unrelated
project files and configuration.

## Implement

1. Import supported APIs from top-level rpacore.
2. Implement cohesive Step.execute(ctx) units; wire explicit order in a
   Transaction with a stable application-owned definition_identity.
3. Keep JSON-safe recovery data in ctx.state; keep live handles in
   ctx.resources and close them explicitly.
4. Validate configuration before filesystem, database, queue, or network
   mutation. Preserve BusinessException versus SystemException and bound retries.
5. For each external effect, identify its operation key, replay verification,
   and uncertain-result policy; test the effect/checkpoint gap.
6. Verify outputs and reloaded durable results when persistence is used.

Never catch a failure merely to report success. Keep credentials and
unnecessary sensitive data out of state, logs, artifacts, reports, and
exception messages.
