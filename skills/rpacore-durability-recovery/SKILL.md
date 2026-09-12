---
name: rpacore-durability-recovery
description: Design and verify durable RPA Core execution and recovery. Use for checkpoints, resume compatibility, external-effect replay, and interruption tests.
---

# Build durable execution and recovery

Run the project's `rpacore version` and compare it with the exact supported
version in [`manifest.toml`](../../manifest.toml). Stop on a mismatch or a
missing manifest; do not guess compatibility from a skill copied on its own.

Read [Durability and Storage](https://github.com/renatomoselli/rpacore/blob/493252649ee6b9d387008e6b7ed41908e2733f46/docs/durability.md) and the
[API reference](https://github.com/renatomoselli/rpacore/blob/493252649ee6b9d387008e6b7ed41908e2733f46/docs/api.md) for checkpoint timing and exact signatures.

## Durable execution

1. Use execute_transaction with transaction_db_path for strict one-off
   checkpoints; use the manifest's database path in an existing project.
2. Give durable work a non-empty application-owned definition_identity.
3. Resume through the Python resume_transaction API with the matching
   identity and concrete steps. It reattaches steps; execute the returned
   transaction explicitly with durable checkpoints.
4. Keep durable fields JSON-safe and runtime resources out of persistence.
   Let checkpoint failures propagate; keep inspection paths read-only.
5. Test reconstructed-process resume, mismatched-identity rejection before
   mutation, and the reloaded final record in a disposable database.

## Derive replay behavior for each external effect

Record the operation identity, affected resource, evidence persisted before
the effect, available deduplication/read-back mechanism, and the uncertain
result disposition. Match the strategy to the operation:

| Effect | Required reasoning |
| --- | --- |
| File replacement | Publish a complete file atomically; verify that existing content belongs to this operation. |
| Append or merge | Recognize a complete owned record; a matching partial prefix is insufficient. |
| Move | Recognize the expected destination and input identity after source disappearance; existence alone is insufficient. |
| External submission | Reuse a supported idempotency key or query acceptance; a timeout does not prove rejection. |

If acceptance cannot be verified, surface that uncertainty for the
application's reconciliation policy; do not automatically repeat the effect.
A different request with the same business key may be a legitimate duplicate
rejection, while replay of the original operation may already be complete.

Test interruption before the effect, after effect-before-checkpoint, and after
checkpoint. Reconstruct from persisted state and verify output ownership,
content, and disposition. Use controlled local targets unless live testing is
authorized. Atomic file publication and a Core checkpoint do not form one
transaction with each other.

Do not derive definition identity from a transaction reference, payload,
deployment, Git commit, or Core version.
