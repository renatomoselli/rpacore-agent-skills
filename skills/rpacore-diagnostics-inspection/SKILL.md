---
name: rpacore-diagnostics-inspection
description: Inspect RPA Core project and transaction health without mutation. Use for doctor, manifests/configuration, transaction or queue evidence, exit codes, and bounded support handoff.
---

# Diagnose and inspect RPA Core

Run the project's `rpacore version` and compare it with the exact supported
version in [`manifest.toml`](../../manifest.toml). Stop on a mismatch or a
missing manifest; do not guess compatibility from a skill copied on its own.

Use the [CLI reference](https://github.com/renatomoselli/rpacore/blob/493252649ee6b9d387008e6b7ed41908e2733f46/docs/cli.md) and
[security guidance](https://github.com/renatomoselli/rpacore/blob/493252649ee6b9d387008e6b7ed41908e2733f46/docs/security.md) for formats and exit codes.

1. State the operator question: which work failed, whether an effect completed,
   whether recovery is compatible, or whether a database is healthy.
2. Start in the automation project with rpacore version and rpacore doctor;
   use --json for machine-readable diagnostics.
3. Use explicit config/database paths when the operator identified them.
   Use transaction list/show/export for the relevant evidence. If the CLI
   cannot filter the desired batch, use the documented public query API;
   do not invent flags or reach directly for private SQL.
4. Distinguish committed records, runtime logs, and unknown external effects.
   An absent completion record alone does not prove an effect never happened.
5. Report the command, exit code, versions, check IDs/statuses, and only the
   approved identifiers needed to answer the question. Label missing evidence.

Doctor and transaction inspection must not create, migrate, or change journal
mode. Exports can contain state and exception details: inspect locally and
select an explicit minimal field set before sharing. Omit raw payloads,
credentials, artifact contents, and free-form exception text by default;
references and paths may also be sensitive. Do not upload evidence implicitly.
