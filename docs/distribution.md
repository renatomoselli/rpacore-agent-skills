# Portable distribution

This repository remains development-only. The commands here build and inspect
local candidates; they do not publish, submit, list, or change repository
visibility.

## Build an immutable candidate

Use Python 3.11 or newer from a clean checkout at the exact reviewed commit:

```powershell
python scripts/package_skills.py build --repo-root . --profile portable --output validation-artifacts/portable --frozen
python scripts/package_skills.py check --repo-root . --profile portable --output validation-artifacts/portable --frozen
```

The output contains a complete seven-skill pack, seven individual folders,
normalized ZIP archives, a schema-versioned inventory, and its SHA-256 file.
`build` refuses to replace an existing output. Choose another output path or,
after inspecting the exact old output, remove that directory explicitly before
retrying, for example:

```powershell
Remove-Item -LiteralPath validation-artifacts/portable -Recurse
```

`check` compares every supplied output byte with a fresh build and never repairs
it. The comparison includes `release-inventory.json` and its adjacent checksum;
those files are immutable handoff records, not an alternate source of truth for
repairing a candidate.
`--frozen` means HEAD-clean: tracked files must equal `HEAD`, and every
non-ignored untracked file also rejects the build. Commit the reviewed source
first, then run the frozen build/check. Untracked files gate intentionally so a
release cannot silently omit local inputs. An output below the source is
allowed only when Git explicitly ignores that path; the documented
`validation-artifacts/` location satisfies that rule. Omitting `--frozen`
permits a development candidate whose inventory sets `working_tree_dirty` to
`true`; that candidate is not release input.

Each skill is self-contained: keep `SKILL.md` and `references/compatibility.json`
together. Compare the installed `rpacore version` with that local resource.
Installing a skill never installs or upgrades RPA Core.
Portable skill folders use an explicit allowlist; hidden metadata such as
`.DS_Store` is rejected rather than silently included.

## Install without changing a user profile

For direct Git use, check out a full 40-character commit, verify the candidate
inventory, and copy either `full/skills/<name>` or `individual/<name>` into an
explicit project-local skill directory. Do not use a mutable branch for a
reproducible install. Before replacement or removal, compare the installed
folder with the recorded inventory and preserve user modifications.

The Skills CLI rehearsal requires Node.js 22.20 or newer, is pinned to
`skills@1.5.25`, uses copy mode and an isolated project, and sets
`DISABLE_TELEMETRY=1`. Its pinned help confirms these project-scope commands:

```powershell
npm exec --yes --package=skills@1.5.25 -- skills add <source> --skill '*' -a opencode -y --copy
npm exec --yes --package=skills@1.5.25 -- skills list -a opencode --json
npm exec --yes --package=skills@1.5.25 -- skills update -p -y
npm exec --yes --package=skills@1.5.25 -- skills remove --skill '*' -a opencode -y
```

On the 2026-09-12 Windows rehearsal, fresh install, list, repeated install, and
remove returned zero. The local-source update reported that there were no
project skills to update. More importantly, repeated `--copy` installation
silently replaced a deliberately modified installed `SKILL.md`. Therefore the
CLI lifecycle is not supported for this candidate: compare installed bytes
against the prior inventory before invoking it, and do not claim its update or
downgrade path until a pinned version passes conflict preservation. Targeted
OpenCode removal retained the shared `.agents/skills` copies associated with
other detected clients; a disposable `remove --all` cleared them. This is a
useful shared-ownership safeguard, but it means a zero exit from targeted
removal does not prove that the folder disappeared.

OpenCode 1.14.30 discovered all seven copied folders with `opencode debug skill`
from the documented project-compatible `.agents/skills/<name>/SKILL.md` path in
an isolated Windows profile. The same documentation also supports the native
`.opencode/skills/<name>/SKILL.md` path. Static discovery proves only that
OpenCode can see and load the files. A configured model must separately pass
the bounded behavior cases in `evaluation-cases.md`; unavailable provider/model
access leaves that row unverified.

## Replace or remove

Treat install, update, downgrade, disable, and removal as distinct operations.
Use the client command and scope recorded by the candidate rehearsal. Refuse a
destructive replacement when installed bytes differ from the prior inventory;
move the modified folder aside for review. Removing one route must not remove a
same-named skill still owned by another route.

SkillsMP and skills.sh discovery are observations, not package-integrity gates.
No directory appearance, ingestion timing, install count, or support claim is
guaranteed by these local instructions.
