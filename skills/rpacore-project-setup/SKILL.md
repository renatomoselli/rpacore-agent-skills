---
name: rpacore-project-setup
description: Set up or upgrade a Python automation project with RPA Core. Use for virtual environments, package installation, rpacore init, generated-project orientation, or dependency upgrades.
---

# Set up an RPA Core project

For an existing project, run its environment's `rpacore version` before making
changes and confirm it satisfies the Core range in the repository's
[`manifest.toml`](../../manifest.toml). For a new project, install the approved
source in the new environment first, then run the same check before scaffolding.
Stop on a mismatch.

Use the public
[tutorial](https://github.com/renatomoselli/rpacore/blob/0a50fcfa31692232b4fe8807997ce026c1e26bf3/docs/tutorial.md),
[CLI reference](https://github.com/renatomoselli/rpacore/blob/0a50fcfa31692232b4fe8807997ce026c1e26bf3/docs/cli.md),
and
[project manifest reference](https://github.com/renatomoselli/rpacore/blob/0a50fcfa31692232b4fe8807997ce026c1e26bf3/docs/project-manifest.md)
for the detailed contract.

## Workflow

1. Verify Python 3.11+ and create a project-local virtual environment.
2. Install RPA Core only from the user-approved source matching the manifest.
   While `published_release = false`, do not claim that PyPI provides the
   compatible development baseline or silently fall back to an older release.
3. Confirm the resolved version with `rpacore version`.
4. Run `rpacore init <project-name>` from the parent directory.
   Stop if the target already exists; do not overwrite it.
5. Inspect `pyproject.toml`, `.gitignore`, `rpacore.toml`, `config.toml`,
   `main.py`, `skills/`, and `tests/`.
6. Run the focused and full generated tests before changing the scaffold.

Keep user automation outside the framework checkout. Do not copy private
framework modules or put credentials in commands, manifests, or committed
configuration. A framework upgrade alone does not require changing an
application-owned `definition_identity`.
