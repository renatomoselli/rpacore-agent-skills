---
name: rpacore-testing-review
description: Test and review RPA Core automations with plain pytest and contract-focused checks. Use for Skill unit tests, persistence/recovery/queue integration tests, retries, idempotency, or public API review.
---

# Test and review an RPA Core automation

Before reviewing code, run `rpacore version` and confirm it satisfies the Core
range in the repository's [`manifest.toml`](../../manifest.toml). Stop on a
mismatch.

Use
[Testing RPA Core Skills](https://github.com/renatomoselli/rpacore/blob/0a50fcfa31692232b4fe8807997ce026c1e26bf3/docs/testing.md),
the
[API reference](https://github.com/renatomoselli/rpacore/blob/0a50fcfa31692232b4fe8807997ce026c1e26bf3/docs/api.md),
and relevant behavior docs for detailed contracts.

## Workflow

1. Unit-test a `Skill` with a plain `ProcessContext`; no framework test base is
   required.
2. Assert outputs, state, artifacts, statuses, and business/system failure.
3. Add integration proof for persistence, resume, queues, reports,
   notifications, or CLI paths the project uses.
4. Use `tmp_path` or another explicit disposable location for SQLite and output
   files; assert reloaded durable records where relevant.
5. Run focused tests first, then `python -m pytest -q` and, from the automation
   project directory, `rpacore doctor`.

Review for top-level `rpacore` imports, stable definition identity, JSON-safe
state, runtime-only resources, bounded/idempotent retries, config validation
before mutation, sensitive-data containment, and read-only inspection. Do not
replace installed-package or integration proof with mocks merely to pass a gate.
