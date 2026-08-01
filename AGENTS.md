# RPA Core Agent Skills — Agent Guide

These rules apply repository-wide.

1. Start with `git status --short --branch`; preserve existing staged and
   unstaged work.
2. Read `README.md`, `manifest.toml`, the affected `skills/*/SKILL.md`, and the
   validator/tests before editing.
3. Keep one portable skill source tree. Harness packages may wrap `skills/` but
   must not own edited copies.
4. Keep skills concise and procedural. Link immutable, version-matched RPA Core
   public documentation instead of copying API tables or framework semantics.
5. Skill frontmatter contains only `name` and `description`. Repository
   compatibility and provenance belong in `manifest.toml`.
6. Do not add hooks, lifecycle scripts, MCP servers, credentials, telemetry,
   Cloud access, runtime AI, pre-authorized permissions, or automatic project
   mutation without a new explicit decision.
7. Run focused tests, then:

   ```powershell
   python scripts\validate_skills.py --repo-root .
   python -m unittest discover -s tests -v
   git diff --check
   ```

8. Do not commit, push, tag, release, publish, or submit a marketplace entry
   without fresh maintainer authorization.
