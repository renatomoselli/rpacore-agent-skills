# RPA Core Agent Skills

Portable guidance for coding agents building RPA Core automations through
supported public APIs.

This companion remains **development-only**, with no supported installation
channel or companion release. Its selected Core baseline is the **released
Core 0.3.0**, at commit
493252649ee6b9d387008e6b7ed41908e2733f46. Compatibility currently means
exactly 0.3.0; later versions need their own validation.

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

## Source and compatibility

The seven directories under skills/ are the single editable instruction source.
Core public documentation owns API and runtime semantics; skills link to the
immutable documentation baseline recorded in [manifest.toml](manifest.toml).
Keep the manifest with the source tree when inspecting or evaluating it.
Copying an isolated skill directory loses its relative compatibility reference.

Before using a skill, compare rpacore version with the manifest. Version text
alone is not consumer proof: the maintainer checks also compare a wheel's
Python files with the selected commit and its installed bytes with that wheel.
The Core published_release flag is independent of companion development status.

Future harness packages may wrap this tree, preserving its manifest and links,
but must not maintain edited copies. Git/project use, Pi/npm, Claude, Codex,
OpenCode, and GitHub Copilot are independent future distribution decisions.
A local validation result does not establish support for any of them.

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

All structural, content, and link rules still apply in write mode. Invalid
content is rejected before the manifest changes. Preserve
`* text=auto eol=lf` in .gitattributes: hashes cover actual UTF-8/LF skill bytes,
and the tool does not silently rewrite CRLF files.

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
