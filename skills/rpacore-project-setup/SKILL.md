---
name: rpacore-project-setup
description: Set up or upgrade an RPA Core automation project. Use for approved package installation, scaffolding, project orientation, and migration of an existing Core project.
---

# Set up or upgrade an RPA Core project

Inspect the existing project's rpacore version before changing it. The exact
version in [references/compatibility.json](references/compatibility.json) defines the target environment.
For new projects, install the approved matching source in a project-local
environment before scaffolding. Verify the target version before applying
its APIs; stop if the compatibility resource is missing or the target does not match.
An explicitly requested upgrade from another version follows the upgrade
workflow below; the source mismatch does not prevent migration assessment.

Use the [tutorial](https://github.com/renatomoselli/rpacore/blob/493252649ee6b9d387008e6b7ed41908e2733f46/docs/tutorial.md),
[CLI reference](https://github.com/renatomoselli/rpacore/blob/493252649ee6b9d387008e6b7ed41908e2733f46/docs/cli.md),
[project manifest reference](https://github.com/renatomoselli/rpacore/blob/493252649ee6b9d387008e6b7ed41908e2733f46/docs/project-manifest.md), and
[durability guide](https://github.com/renatomoselli/rpacore/blob/493252649ee6b9d387008e6b7ed41908e2733f46/docs/durability.md).

## New project

1. Verify Python 3.11+ and create a project-local virtual environment.
2. Install Core from the user-approved source matching the compatibility resource.
   Core's published_release flag describes Core, not companion availability.
3. Run rpacore init <project-name> from the parent directory. Stop if the
   target exists; use the existing-project workflow instead of overwriting it.
4. Inspect pyproject.toml, rpacore.toml, config.toml, main.py, steps/, tests/,
   and .gitignore. Run the generated tests before changing the scaffold.
5. Run the project from its own directory and inspect its declared outputs
   and persisted result.

## Existing Core project / upgrade

Use the source-version documentation to assess migration and establish the
approved target environment before following target APIs.

- Inventory public imports, dependency versions, definition identities, and
  retained transaction/queue databases. Separate framework upgrade from a
  business-definition change.
- Stop workers and use disposable copies for the documented offline migration
  and paired database/code rollback rehearsal before touching retained work.
- For a pre-Step project, migrate the execution API and wiring to Step and
  steps/ using the selected version's docs; do not blindly rename agent skills
  or invent persisted schema transformations.
- Verify public imports, project tests, business-output parity, and persisted
  recovery compatibility in the target environment. Legacy work without a
  required identity must remain explicitly non-resumable; never backfill one
  merely to bypass rejection.
- Record the source/target versions, checks run, remaining recovery limits,
  and the rollback evidence. Preserve unrelated changes.

A framework upgrade alone does not require changing definition_identity.
Keep user automation outside the framework checkout and credentials out of
commands, manifests, and committed configuration.
