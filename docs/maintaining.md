# Maintaining the companion

## Edit and validate

Keep each skill instruction-only, with name and description frontmatter.
Prefer extending an existing workflow over creating another skill for a small
variation. Link immutable Core public docs instead of copying API tables.

1. Review the skill change and its intended request examples.
2. Run python scripts/validate_skills.py --repo-root . --write.
3. Inspect the diff: regeneration may change sha256 values only.
4. Run static validation and python -m unittest discover -s tests -v.
5. Run the affected consumer/evaluation scenarios below.

The LF .gitattributes contract applies on Windows too. The hash writer rejects
CRLF, invalid links, malformed metadata, and forbidden content before updating
the manifest. It writes the manifest atomically and leaves unrelated fields
unchanged. It does not approve the instruction's meaning.

## Verify an installed consumer

Use a disposable checkout at the exact manifest Core commit. The same entrypoint
used by CI builds its wheel and prepares isolated build and consumer environments:

From the companion repository, with that checkout at ../core-baseline:

```powershell
python scripts/check_core_baseline.py core-ref
python scripts/check_core_baseline.py verify --core-repo ../core-baseline
```

The first command prints the validated manifest's Core commit for selecting the
checkout; it does not clone or mutate a repository. The second creates
validation-artifacts/run-<unique>/ with wheels/, build-venv/, consumer-venv/,
and a success-only consumer.json. It prints the chosen run directory before
building. Repeating it retains previous evidence and uses fresh environments
and wheels. A failed run remains inspectable without a success receipt.

Use --evidence-root with verify to choose another artifact parent. Build tools
and pytest are installed only into the new environments; package installation
needs network access or an appropriately configured package cache. The caller's
Python environment is not modified. Core has no runtime dependency requirement
for these scenarios.

When a matching wheel and consumer environment already exist, invoke
scripts/verify_consumer.py directly with --repo-root, --core-repo, --wheel,
--python and a new --receipt path. The receipt parent must already exist.
Receipt files are exclusive writes and are never overwritten.

The verifier:

- validates the companion and exact Core checkout/documentation targets;
- compares the wheel's complete Python file set and source with that commit,
  allowing only CRLF-to-LF normalization for source comparison;
- verifies actual installed Python-file bytes against the selected wheel;
- runs public-API reference consumers, generated-project tests, and a real
  interrupted-process recovery scenario in disposable directories;
- writes hashes for the manifest, skills, wheel, and verification scripts,
  plus environment identity and results, only after successful checks.

The reference publication fixture assumes one writer per destination. It
demonstrates operation-owned replay, not general concurrent file coordination.
An unchanged version string does not establish artifact identity. Reject a
stale wheel rather than adapting fixtures to an obsolete API.

To revalidate a saved receipt against the same inputs, use --check-receipt
instead of --receipt. It reruns the checks and rejects stale or different
evidence. A changed instruction, verifier, wheel, or environment requires a
fresh result; do not edit a receipt to make it agree.

Receipt identity deliberately includes the Python patch version, pytest version,
absolute Python executable path, and installed Core path. Moving or recreating
the environment requires a new receipt after verification; --check-receipt
asserts the same complete environment and inputs, not portability of old
evidence. The generated-project scenario intentionally checks the scaffold of
the exact selected Core release; a baseline upgrade must revisit those checks.

## Change the Core baseline

Select a released Core version and exact commit explicitly. The manifest
currently accepts one exact ==x.y.z version, so it does not advertise an
untested future minor or patch range.

Update commit, docs_base, version_spec, and the fact of Core published_release
together. Update every skill's documentation links and API vocabulary.
Companion status remains development-only until a separate release decision;
a published Core release does not release the companion.

Review the README, changelog, and fixtures for implementation accuracy.
Regenerate skill hashes, run the complete static suite and exact installed
consumer checks, and retain a new receipt. Existing-project migrations must
also prove the selected source-to-target durable compatibility on disposable
copies; do not infer that from latest-version consumer tests.

A distribution proposal additionally needs the chosen harness, installed
layout preserving manifest/document links, realistic request evaluations,
ownership, and release policy. Each channel requires its own decision and
proof. Maintainer validation does not install, publish, or authorize one.

## CI and evidence

CI validates static rules and maintainer tests on Windows and Linux. The pinned
baseline job calls scripts/check_core_baseline.py to build the selected Core
checkout, install its wheel into a separate environment, and run reference
consumers. Its JSON receipt is printed in the job log and written under
validation-artifacts/run-<unique>/. Workflow YAML does not own build or receipt
orchestration.

Reference tests prove maintained example behavior against an installed
artifact. They do not prove that an arbitrary model follows the skill or that
a supported distribution channel exists. Use the separate evaluation cases
when evaluating actual agent-generated output.
