# RPA Core Agent Skills

Portable guidance for coding agents building RPA Core automations through
supported public APIs.

This companion has stable source identity **0.1.1**. Its selected Core baseline
is the **released Core 0.3.0**, at commit
493252649ee6b9d387008e6b7ed41908e2733f46. Compatibility currently means
exactly 0.3.0; later versions need their own validation.

Publication is tracked separately from source identity. The immutable `v0.1.0`
assets remain intact, but their post-publication Linux rebuild exposed
platform-dependent DEFLATE output. The supported public channel becomes
`v0.1.1` on the
[GitHub releases page](https://github.com/renatomoselli/rpacore-agent-skills/releases)
only after it and its ten documented assets pass both hosted platforms. Until
then, do not substitute default-branch HEAD or GitHub-generated source archives.

## Choose a workflow

| Request | Start with | Result to establish |
| --- | --- | --- |
| Design an automation from a business process | [Automation development](skills/rpacore-automation-development/SKILL.md) | Unit of work, execution mode, durable inputs, failure policy, completion evidence |
| Adopt Core in an existing script | [Automation development](skills/rpacore-automation-development/SKILL.md) | Incremental conversion with business-output parity and explicit replay limits |
| Create or upgrade a Core project | [Project setup](skills/rpacore-project-setup/SKILL.md) | Matching environment, current scaffold, or tested migration/rollback path |
| Make work recoverable | [Durability and recovery](skills/rpacore-durability-recovery/SKILL.md) | Persisted recovery contract and effect-by-effect replay verification |
| Build local queue processing | [Queue processing](skills/rpacore-queue-processing/SKILL.md) | Stable work identity, ownership, retries, and truthful acknowledgement |
| Investigate a failed run | [Diagnostics and inspection](skills/rpacore-diagnostics-inspection/SKILL.md) | Bounded evidence answering a named operator question |
| Publish reports or notifications | [Reporting and notifications](skills/rpacore-reporting-notifications/SKILL.md) | Output publication and delivery truth without unnecessary sensitive data |
| Test or review an automation | [Testing and review](skills/rpacore-testing-review/SKILL.md) | Evidence for the requested scope; a broad review also evaluates useful improvements |

Use the relevant route for the request. A small change need not run every
workflow, and a narrow defect review need not become product discovery.

## Install the stable portable release

Use the attached portable ZIPs, not GitHub's automatically generated source
archive. Download the full pack plus `release-inventory.json` and
`release-inventory.sha256`, verify both the inventory checksum and the ZIP's
SHA-256 entry, then extract and copy only the selected skill folders into an
explicit project-local directory. Never overwrite an existing folder until
you have compared it with the prior inventory and preserved local changes.

The exact Windows commands, individual-skill route, removal procedure, and
bounded preview `gh skill install --pin v0.1.1` path are in
[portable distribution](docs/distribution.md). Installation never installs or
upgrades RPA Core.

## Source and compatibility

The seven directories under skills/ are the single editable instruction source.
Core public documentation owns API and runtime semantics; skills link to the
immutable documentation baseline recorded in the schema-version-2
[manifest.toml](manifest.toml).
Each canonical folder includes a generated `references/compatibility.json`
derived from that manifest, so a validated folder remains self-contained when
copied without its parent repository.

Before using a detached skill, compare `rpacore version` with its local
`references/compatibility.json`. Version text
alone is not consumer proof: the maintainer checks also compare a wheel's
Python files with the selected commit and its installed bytes with that wheel.
The Core `published_release` flag is independent of companion release status.

Portable packages mechanically copy this tree and must not maintain edited
instructions. See [portable distribution](docs/distribution.md) and the
[release dossier](docs/portable-release-dossier.md). Git/project use,
Pi/npm, Claude, Codex, OpenCode, and GitHub Copilot remain independently
verified support decisions; a local validation result establishes none of them.

## Maintainer validation

Python 3.11+ is required for repository tooling. From this repository:

```powershell
python scripts/validate_skills.py --repo-root .
python -m unittest discover -s tests -v
git diff --check
```

After reviewing a skill edit, regenerate only its manifest hash:

```powershell
python scripts/validate_skills.py --repo-root . --write
```

All structural, content, and link rules still apply in write mode. Missing
generated compatibility resources are bootstrapped; invalid pending output is
rejected before any generated compatibility resource or manifest hash changes.
The final replacements roll back together if a late write or validation fails.
Preserve `* text=auto eol=lf` in .gitattributes: hashes cover actual UTF-8/LF
skill bytes, and the tool does not silently rewrite CRLF files.

Use the [maintainer guide](docs/maintaining.md) for exact-baseline checks,
installed-wheel consumer scenarios, evidence receipts, and baseline updates.
The [evaluation cases](docs/evaluation-cases.md) distinguish executable
reference consumers from actual agent-output evaluation.

## Scope and security

Skills are instructions and can influence powerful development tools. Review
their contents before use and preserve the user's task and authorization scope.
They add no automation runtime, hooks, MCP server, credentials, telemetry, or
implicit permission to mutate projects or contact external systems.

Maintainer scripts and tests live outside skills/ and run only when explicitly
invoked. See [SECURITY.md](SECURITY.md) for private reporting guidance.
