# RPA Core Agent Skills

Portable, task-focused guidance that helps coding agents build RPA Core
automations with supported public contracts.

> [!WARNING]
> This repository is a development-only foundation. It targets the unreleased
> RPA Core `0.3.x` development line and has no supported package, plugin,
> marketplace entry, or release. The latest published RPA Core version is not
> compatible with these draft skills.

## Purpose

RPA Core's public documentation owns framework APIs and behavior. This
repository owns concise agent workflows and high-risk guardrails. Skills link
to one immutable Core documentation baseline instead of copying API tables,
durability rules, or CLI references.

The skills cannot change automation runtime behavior. They install no Python
package and include no hooks, lifecycle scripts, MCP server, credentials,
telemetry, Cloud access, runtime AI, or pre-authorized tool permissions.

## Skills

- `rpacore-project-setup`
- `rpacore-automation-development`
- `rpacore-durability-recovery`
- `rpacore-queue-processing`
- `rpacore-diagnostics-inspection`
- `rpacore-reporting-notifications`
- `rpacore-testing-review`

Each directory under `skills/` is the only editable source for that skill.
Future harness packages may wrap this tree but must not maintain copied bodies.
The repository follows the open
[Agent Skills specification](https://agentskills.io/specification).

## Compatibility and provenance

[`manifest.toml`](manifest.toml) records the companion version, development
status, supported Core range, exact Core commit, immutable documentation base,
and SHA-256 for every skill. Before using a skill, run `rpacore version` and
confirm that it satisfies the manifest's supported range.

The current Core baseline is intentionally a development commit, not a release
tag. Promotion or release requires replacing it with the explicitly selected
tag/commit and revalidating every skill and documentation target.

## Validation

Python 3.11 or newer is required only for repository validation:

```powershell
python scripts\validate_skills.py --repo-root .
python scripts\validate_skills.py --repo-root . --core-repo ..\rpacore
python -m unittest discover -s tests -v
git diff --check
```

The optional `--core-repo` check requires that checkout to be at the exact Core
commit recorded by the manifest and proves that every linked documentation file
exists there.

The pinned-baseline CI job uses the repository's standard GitHub token when the
Core repository is public. While Core is private, maintainers must configure an
`RPACORE_READ_TOKEN` Actions secret containing a fine-grained token limited to
that repository with read-only Contents access. The workflow does not persist
the credential after checkout.

## Installation and distribution

No supported installation channel exists yet. Git/project use, Pi/npm, Claude,
Codex, OpenCode, and GitHub Copilot distribution are separate future decisions
that require target-specific validation. Do not infer support from a shared
directory convention.

## Security

Skills are instructions and can influence powerful development tools. Review
their contents before use, keep tool approval under user control, and see
[SECURITY.md](SECURITY.md) for private reporting guidance.
