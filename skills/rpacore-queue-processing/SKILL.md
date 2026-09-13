---
name: rpacore-queue-processing
description: Build and review local RPA Core queue producers and consumers. Use for SqliteQueue, stable enqueue identity, run_queue_loop, lease loss, retries, poison handling, and external-effect acknowledgement.
---

# Build queue processing

Run the project's `rpacore version` and compare it with the exact supported
version in [`references/compatibility.json`](references/compatibility.json).
Stop on a mismatch or a missing resource; do not guess compatibility.

Read the queue sections of the [API reference](https://github.com/renatomoselli/rpacore/blob/493252649ee6b9d387008e6b7ed41908e2733f46/docs/api.md) and
[durability guide](https://github.com/renatomoselli/rpacore/blob/493252649ee6b9d387008e6b7ed41908e2733f46/docs/durability.md) for provider and fencing contracts.

1. Design for at-least-once delivery; never claim exactly-once external effects.
2. Construct QueueItem(reference=<stable-key>, payload={...}) and use
   SqliteQueue.add_once when duplicate enqueue requests represent the same work.
   Define whether changed input under the same filename/business key is new work.
3. Keep queue references separate from transaction definition identity.
4. Let run_queue_loop own claim, renewal, attempt, revision, transaction,
   and completion fencing.
5. Before acknowledging success, identify how each external effect is verified
   on replay. Distinguish the same operation from a conflicting submission.
6. Test redelivery, terminal/poison failure, lease loss, stale claim rejection,
   and durable attempts in disposable databases. Test the supported retry
   policy; do not invent delayed-delivery APIs absent from the selected version.
7. Report QueueRunSummary failures and uncertain transitions as well as
   completed counts; distinguish processing outcome from notification delivery.

After ownership is lost, do not acknowledge success or mutate the item as if
the consumer still held the claim. A retry decision must account for effects
that may already have happened. This workflow concerns local queue consumers;
it does not specify a remote worker protocol.
