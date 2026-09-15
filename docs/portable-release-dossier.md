# Portable release dossier

This is the reviewed handoff for preparing the corrective portable `v0.1.1`
release. Stable source identity does not prove that a public release exists.
This file does not authorize a tag, GitHub release, repository setting or
metadata change, directory submission, telemetry, profile mutation, or native
client wrapper.

## Frozen identity

- Product: RPA Core Agent Skills, seven skills
- Companion version/status: `0.1.1`, stable
- License: Apache-2.0; release artifacts include `LICENSE` and `NOTICE`
- Core: exactly `0.3.0` at
  `493252649ee6b9d387008e6b7ed41908e2733f46`
- Source and artifacts: use the full commit and SHA-256 values in the generated
  `release-inventory.json`; require tracked files to equal `HEAD` with no
  non-ignored untracked files, and reject `working_tree_dirty: true` for release
- Support route: repository issue and private security routes documented in
  `README.md` and `SECURITY.md`

## Proposed GitHub release

- Tag/title: annotated `v0.1.1`; release title `RPA Core Agent Skills v0.1.1`
- Target: the future clean release-source commit embedded in the final frozen
  inventory; never mutable branch state
- Description: `Portable agent skills for building reliable Python automations with RPA Core.`
- Homepage: leave unset
- Generic topics: `rpa`, `python`, `automation`, `durable-execution`
- Listing-triggering topic, authorized separately: `agent-skills`
- Support: public issues and the private vulnerability-reporting route in
  `SECURITY.md`
- Notes: `docs/release-notes-v0.1.1.md`

The ten allowlisted assets are `rpacore-agent-skills-portable.zip`, the seven
manifest-named individual skill ZIPs, `release-inventory.json`, and
`release-inventory.sha256`. Upload them only from the final frozen build. The
release CLI must use the existing annotated tag plus `--verify-tag`, create a
draft with all assets, and leave that draft inspectable before publication.

Before publication, a failed candidate is discarded and rebuilt from a new
clean commit; removal of any draft or tag is a separately authorized action.
The immutable `v0.1.0` tag and assets remain untouched. Their hashes and
payloads passed verification, but Linux could not reproduce the Windows-built
DEFLATE archive bytes. Version `v0.1.1` changes archive members to `ZIP_STORED`
and must pass the complete release sequence again. After publication, never
replace either release, tag, or asset set; publish another corrected version if
needed.

## Release description

Portable instructions for designing, testing, diagnosing, and recovering
deterministic RPA Core automations through supported public APIs. The package
contains no runtime AI, hooks, MCP server, credentials, telemetry, framework
installer, or automatic project mutation.

Search terms: RPA Core, Python automation, durable execution, queue processing,
recovery, diagnostics, reporting, testing.

## Evidence matrix

| Surface | Status | Required evidence before support claim |
| --- | --- | --- |
| Portable folders and ZIPs | `v0.1.0` payload integrity passed; Linux byte rebuild failed; `v0.1.1` pending | Stored-archive clean commit, deterministic build, and non-repairing check pass on both hosted platforms |
| Exact Core consumer | `v0.1.0` source CI passed; `v0.1.1` rerun pending | Repeat all five installed-wheel scenarios from the exact Core baseline on both hosted platforms |
| Direct immutable Git copy | `v0.1.0` public; `v0.1.1` pending | Verify the corrected immutable public commit install and retain lifecycle boundaries |
| Skills CLI 1.5.25 | failed | Telemetry-disabled fresh/list/repeat/remove passed, but repeat copy silently overwrote a modified skill; update had no local project entry |
| OpenCode 1.14.30 discovery | Windows passed | All seven installed folders discovered from isolated `.agents/skills`; Linux remains unrun |
| OpenCode behavior | unverified | Configured model passes the bounded development, recovery, inspection, and negative-control cases |
| SkillsMP / skills.sh appearance | not observed | Public-source indexing observation after separately authorized release; no guaranteed listing |
| Other portable clients | unverified | Primary client documentation and every applicable shared gate at a recorded version |

Candidate readiness, publication authorization, release reachability, listing, and
verified public installation must be recorded separately. Native Pi, Claude,
Codex/Cursor/Copilot, and Gemini metadata belong to their later channel work.

BL-060's new-shared-tool trigger fired when public-asset verification was added.
The bounded extraction is complete here: `verify_release.py` owns release
reconstruction, consumes the packager's canonical archive map and file walker,
and uses shared test-repository support. The remaining optional cleanup family
stays deferred because the package profile and distributed-resource/hash shape
did not change.

After publication, manually dispatch `.github/workflows/verify-release.yml`.
It checks out the explicit tag input, downloads the public assets with read-only
contents permission, requires the manifest-derived asset allowlist,
reconstructs the full package for `check --frozen`, and verifies all seven
full-pack plus individual-skill copies in runner-local disposable directories
on Windows and Ubuntu.

## Release checklist

1. Select a clean stable companion commit and rerun static, test, `build --frozen`,
   `check --frozen`, cross-platform ten-asset `compare`, exact-Core, installed-wheel, Windows, and Linux gates.
2. Record the inventory and archive digests plus the client/OS commands and
   transcripts. Confirm cached local resources remain readable offline.
3. Confirm owner, initial release version, immutable tag, publisher coordinates,
   support contact, replacement/deprecation procedure, and destination payload.
4. Obtain separate authorization for each publication or listing-triggering
   action. Keep the clean release-source commit, annotated tag, and ten-asset
   draft contiguous; if the external gate cannot proceed, the supported public
   channel remains unavailable rather than falling back to branch HEAD.
5. After publication, dispatch the release-verification workflow with the exact
   tag and attach its run URL plus both OS job conclusions to private evidence.
