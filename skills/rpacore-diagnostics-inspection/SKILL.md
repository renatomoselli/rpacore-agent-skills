---
name: rpacore-diagnostics-inspection
description: Diagnose and inspect an RPA Core project safely. Use for rpacore doctor, manifests/config, transaction or queue health, transaction inspection/export, exit codes, or privacy-bounded support evidence.
---

# Diagnose and inspect RPA Core

Before inspecting the project, run `rpacore version` and confirm it satisfies
the Core range in the repository's [`manifest.toml`](../../manifest.toml). Stop
on a mismatch.

Use the public
[CLI reference](https://github.com/renatomoselli/rpacore/blob/0a50fcfa31692232b4fe8807997ce026c1e26bf3/docs/cli.md)
and
[security guidance](https://github.com/renatomoselli/rpacore/blob/0a50fcfa31692232b4fe8807997ce026c1e26bf3/docs/security.md)
for check IDs, formats, and exit codes.

## Workflow

1. Start from the automation project with `rpacore version` and
   `rpacore doctor`; use `--json` for machine-readable results.
2. Select explicit config/database paths only when the operator identified the
   intended files.
3. Use `rpacore transaction list/show/export` for transaction evidence.
4. Report bounded versions, check IDs/statuses, the command, and exit code.

Doctor and transaction inspection must not create, migrate, or change journal
mode while diagnosing. Do not expose credentials, raw payloads, state,
exception secrets, or artifact contents. Treat exports as potentially
sensitive data.
