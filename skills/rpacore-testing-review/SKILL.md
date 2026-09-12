---
name: rpacore-testing-review
description: Test and review RPA Core automations against public contracts. Use for Step tests, persistence/recovery/queue integration, regressions, or an explicitly requested broad improvement review.
---

# Test and review an RPA Core automation

Run the project's `rpacore version` and compare it with the exact supported
version in [`manifest.toml`](../../manifest.toml). Stop on a mismatch or a
missing manifest; do not guess compatibility from a skill copied on its own.

Use [Testing RPA Core Steps](https://github.com/renatomoselli/rpacore/blob/493252649ee6b9d387008e6b7ed41908e2733f46/docs/testing.md),
the [API reference](https://github.com/renatomoselli/rpacore/blob/493252649ee6b9d387008e6b7ed41908e2733f46/docs/api.md), and relevant behavior docs.

## Test the requested behavior

1. Unit-test a Step with a plain ProcessContext and ordinary pytest.
2. Assert outputs, state, artifacts, statuses, and business/system failure.
3. Add integration proof for persistence, resume, queues, reports,
   notifications, or CLI paths the project actually uses.
4. Use disposable SQLite/output locations and assert reloaded durable records.
   For external effects, test reconstructed replay across the effect/checkpoint
   gap as well as ordinary failure.
5. Run focused tests and the relevant project suite. Use installed-package
   proof for consumer compatibility and doctor for applicable diagnostics.

Review top-level imports, stable definition identity, JSON-safe state,
runtime-only resources, retry boundaries, config validation before mutation,
sensitive-data containment, and read-only inspection. Mocks do not substitute
for the installed-package or integration contract being assessed.

## Match review breadth to the request

Keep a targeted defect/regression review focused. When the user asks for a
broad or proactive review, also examine missing user workflows, operator
friction, API usability, documentation, and useful application functionality.

For each defect, give a concrete trigger, consequence, source pointer, and
reproduction or meaningful test. For each opportunity, give the user workflow,
current capability boundary, bounded proposal, tradeoff, and a way to test
its value. Distinguish proven gaps from demand/performance hypotheses and
existing deferred work. Respect recorded decisions and requested scope.

Report what changed or was inspected, which checks actually ran, and the
remaining limitations. Passing static skill validation proves neither that
agent-generated code works nor that a distribution channel is supported.
