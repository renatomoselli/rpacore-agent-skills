# Portable candidate dossier

This is a no-publish handoff for the shared portable package. It does not
authorize a Git release, directory submission, telemetry, profile mutation, or
native client wrapper.

## Frozen identity

- Product: RPA Core Agent Skills, seven skills
- Companion version/status: `0.1.0-dev.0`, development-only
- License: Apache-2.0; candidate includes `LICENSE` and `NOTICE`
- Core: exactly `0.3.0` at
  `493252649ee6b9d387008e6b7ed41908e2733f46`
- Source and artifacts: use the full commit and SHA-256 values in the generated
  `release-inventory.json`; require tracked files to equal `HEAD` with no
  non-ignored untracked files, and reject `working_tree_dirty: true` for release
- Support route: repository issue and private security routes documented in
  `README.md` and `SECURITY.md`

## Candidate description

Portable instructions for designing, testing, diagnosing, and recovering
deterministic RPA Core automations through supported public APIs. The package
contains no runtime AI, hooks, MCP server, credentials, telemetry, framework
installer, or automatic project mutation.

Search terms: RPA Core, Python automation, durable execution, queue processing,
recovery, diagnostics, reporting, testing.

## Evidence matrix

| Surface | Status | Required evidence before support claim |
| --- | --- | --- |
| Portable folders and ZIPs | Windows and Ubuntu candidate gates passed | Clean-commit validation, tests, deterministic build, and non-repairing check pass on both hosted platforms; the exact run and source identity are recorded in the private closeout evidence |
| Exact Core consumer | Windows and Ubuntu passed | Five installed-wheel scenarios pass from the exact Core baseline on both hosted platforms; the exact run and source identity are recorded in the private closeout evidence |
| Direct immutable Git copy | partial | Isolated local Git source used; immutable public commit install and full upgrade/downgrade lifecycle remain |
| Skills CLI 1.5.25 | failed | Telemetry-disabled fresh/list/repeat/remove passed, but repeat copy silently overwrote a modified skill; update had no local project entry |
| OpenCode 1.14.30 discovery | Windows passed | All seven installed folders discovered from isolated `.agents/skills`; Linux remains unrun |
| OpenCode behavior | unverified | Configured model passes the bounded development, recovery, inspection, and negative-control cases |
| SkillsMP / skills.sh appearance | not observed | Public-source indexing observation after separately authorized release; no guaranteed listing |
| Other portable clients | unverified | Primary client documentation and every applicable shared gate at a recorded version |

Directory readiness, publication authorization, submission, listing, and
verified public installation must be recorded separately. Native Pi, Claude,
Codex/Cursor/Copilot, and Gemini metadata belong to their later channel work.

## Release checklist

1. Select a clean companion commit and rerun static, test, `build --frozen`,
   `check --frozen`, exact-Core, installed-wheel, Windows, and Linux gates.
2. Record the inventory and archive digests plus the client/OS commands and
   transcripts. Confirm cached local resources remain readable offline.
3. Confirm owner, initial release version, immutable tag, publisher coordinates,
   support contact, replacement/deprecation procedure, and destination payload.
4. Obtain separate authorization for each publication or listing-triggering
   action. Verify public installation only after that action succeeds.
