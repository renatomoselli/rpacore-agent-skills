# RPA Core Agent Skills v0.1.1

RPA Core Agent Skills gives coding agents practical guidance for building
reliable Python automations with RPA Core. Version 0.1.1 is the first release
people should use; it supersedes v0.1.0.

## What's included

The collection includes seven skills covering:

- designing a new automation or adopting RPA Core in an existing script;
- creating, upgrading, and reviewing RPA Core projects;
- recovery, retries, durable execution, and local queue processing;
- diagnostics, reporting, notifications, and testing.

You can download the complete collection or choose an individual skill. Every
skill is self-contained and records the exact RPA Core version it supports.

## Install

Choose the full collection or download just the skill you need from the files
attached to this release. Avoid GitHub's automatically generated source-code
archives.

Every attached ZIP includes an `INSTALL.md` with the verification and
installation steps, along with the license and notice files.

## Compatibility

These skills are made for RPA Core 0.3.0 exactly. Installing them does not
install or upgrade RPA Core.

## Why v0.1.1?

Version 0.1.0 was published, but its final Linux verification found that the
ZIP files did not rebuild byte-for-byte on Linux the way they did on Windows.
The downloads themselves were intact, but differences in compression and file
ordering meant the release did not meet our cross-platform reproducibility
requirement.

Version 0.1.1 stores the ZIP contents without compression and uses the same
explicit file order on every platform. The downloads are slightly larger; the
seven skill instructions and their behavior are unchanged.

The immutable v0.1.0 release remains available as part of the project's
history, but v0.1.1 is the version to install.

## Support

This release covers the portable downloads. Preview installers, individual
assistant integrations, and marketplace availability have their own support
status.

Found a problem? Open an issue in this repository. For security concerns, use
the private reporting route described in `SECURITY.md`.
