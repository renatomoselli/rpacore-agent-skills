---
name: rpacore-durability-recovery
description: Implement and review durable execution, checkpoints, persistence, and resume compatibility. Use with execute_transaction, resume_transaction, definition_identity, SQLite history, or crash recovery tests.
---

# Build durable execution and recovery

Before changing code, run `rpacore version` and confirm it satisfies the Core
range in the repository's [`manifest.toml`](../../manifest.toml). Stop on a
mismatch.

Read
[Durability and Storage](https://github.com/renatomoselli/rpacore/blob/0a50fcfa31692232b4fe8807997ce026c1e26bf3/docs/durability.md)
and the
[API reference](https://github.com/renatomoselli/rpacore/blob/0a50fcfa31692232b4fe8807997ce026c1e26bf3/docs/api.md)
for checkpoint timing, schemas, and exact signatures.

## Workflow

1. Use `execute_transaction(...)` with
   `transaction_db_path=manifest.transaction_db_path` when one-off work needs
   strict checkpoints.
2. Give durable work a non-empty application-owned `definition_identity`.
3. Pass the exact same identity to `resume_transaction(...)`; incompatible or
   unidentified non-successful work fails closed before recovery mutation.
4. Keep durable fields JSON-safe and runtime resources out of persistence.
5. Let checkpoint failures propagate and keep inspection paths read-only.
6. Test failure after a known checkpoint, reconstructed-process resume,
   mismatched-identity rejection, and the reloaded final record using a
   disposable database.

Do not derive definition identity from a transaction reference, payload,
deployment, Git commit, or RPA Core version.
