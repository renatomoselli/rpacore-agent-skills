# Security Policy

RPA Core Agent Skills contains development instructions, not a sandbox. A skill
can influence an agent that has filesystem, shell, network, or repository
access. Keep tool approval under user control and inspect skill changes before
installation or use.

## Supported versions

The stable companion line begins with `v0.1.0`. Version `v0.1.0` remains
immutable but is superseded because its cross-platform post-publication byte
rebuild did not pass. Version `v0.1.1` becomes the supported release only after
its immutable public assets pass that Windows/Linux gate; default-branch
snapshots and development builds are not supported releases. Report issues
against the exact tag and installed artifact digest whenever possible.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting flow when available:

<https://github.com/renatomoselli/rpacore-agent-skills/security/advisories/new>

If that route is unavailable, open a public issue requesting a private contact.
Do not include exploit details, credentials, customer data, private repository
contents, or infrastructure names in the issue.

Include the affected companion commit, skill name, harness if relevant, a
non-sensitive reproduction, and the unsafe action or disclosure that could
result.

## Boundary

Reports about the RPA Core Python framework belong in the
[RPA Core repository](https://github.com/renatomoselli/rpacore). Harness,
marketplace, package-manager, or user-authored automation issues may be
redirected when this repository does not own the affected behavior.
