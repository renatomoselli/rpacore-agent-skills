---
name: rpacore-queue-processing
description: Build and review RPA Core queue producers and workers. Use with SqliteQueue, add_once, run_queue_loop, leases, retries, poison handling, fencing, idempotency, or queue-backed transactions.
---

# Build queue processing

Before changing code, run `rpacore version` and confirm it satisfies the Core
range in the repository's [`manifest.toml`](../../manifest.toml). Stop on a
mismatch.

Read the queue sections of the public
[API reference](https://github.com/renatomoselli/rpacore/blob/0a50fcfa31692232b4fe8807997ce026c1e26bf3/docs/api.md)
and
[durability guide](https://github.com/renatomoselli/rpacore/blob/0a50fcfa31692232b4fe8807997ce026c1e26bf3/docs/durability.md)
for exact provider and fencing contracts.

## Workflow

1. Design for at least once delivery; never claim exactly once behavior.
2. Construct `QueueItem(reference=<stable-key>, payload={...})` and pass it to
   `SqliteQueue.add_once(item)` when duplicate enqueue requests represent the
   same work.
3. Keep queue references separate from transaction definition identity.
4. Let `run_queue_loop(...)` own claim, renewal, attempt, revision, transaction,
   and completion fencing.
5. Protect external effects with application idempotency before acknowledging
   success.
6. Test redelivery, retry scheduling, terminal/poison failure, lease loss,
   stale claim rejection, and durable attempts in disposable databases.

After ownership is lost, do not acknowledge success or mutate the item as if
the worker still held the claim.
