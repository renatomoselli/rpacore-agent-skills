# RPA Core Agent Skills v0.1.0

The first stable RPA Core Agent Skills release provides seven portable,
self-contained skills for designing, setting up, testing, diagnosing, and
recovering Python automations built with RPA Core 0.3.0.

## Included

- A full seven-skill portable ZIP and seven individual-skill ZIPs.
- Skill-local generated compatibility resources pinned exactly to released
  RPA Core 0.3.0 at commit
  `493252649ee6b9d387008e6b7ed41908e2733f46`.
- A deterministic release inventory and adjacent SHA-256 checksum.
- Apache-2.0 license and notice files in every portable package.
- Immutable manual-download guidance and a bounded preview GitHub Skills path.

Download attached assets rather than GitHub-generated source archives. Verify
`release-inventory.json` with `release-inventory.sha256`, then verify the chosen
ZIP against its inventory entry before extracting it. Full commands and safe
replacement/removal guidance are in the `INSTALL.md` included with every
attached ZIP.

## Support boundaries

- Installing these skills does not install or upgrade RPA Core.
- Compatibility is exact: RPA Core `==0.3.0` only.
- GitHub CLI Skills support is preview functionality. The required public-tag
  release check pins `v0.1.0` and uses an explicit disposable directory.
- `skills@1.5.25` is not supported for repeat install, update, or downgrade:
  rehearsal showed that repeat copy can silently overwrite a modified skill.
- A pre-release OpenCode folder-discovery rehearsal passed on Windows, but the
  public tag, model behavior, and Linux discovery remain unverified.
- Pi/npm, Claude, Codex/Cursor/Copilot plugin, Gemini, SkillsMP, and skills.sh
  publication or ranking are not part of this release.

Report ordinary problems through the repository issue tracker. Report security
problems through the private route documented in `SECURITY.md`.
