# Changelog

All notable user-facing changes to RPA Core Agent Skills will be recorded here.

## 0.1.1 - prepared 2026-09-14

### Fixed

- Store normalized ZIP members without DEFLATE compression so Windows and
  Linux rebuild the same archive, inventory, and checksum bytes. Version 0.1.0
  assets and payload hashes remain intact, but its post-publication Linux
  byte-rebuild gate exposed platform-dependent zlib output.

## 0.1.0 - 2026-09-14

### Added

- Added the portable repository foundation, seven RPA Core skills,
  deterministic compatibility/hash manifest, and static validation.

### Changed

- Promote the companion identity from development-only `0.1.0-dev.0` to stable
  `0.1.0`; publication and public-install proof remain separately recorded.
- Align all seven skills and immutable documentation links with released Core
  0.3.0 and its Step API.
- Add business-process design, incremental script adoption, existing-project
  upgrades, effect-by-effect replay decisions, and scope-aware broad reviews.
- Add request routing, exact-baseline consumer verification and evidence
  receipts, hash-only regeneration, and maintainer/evaluation guidance.
- Make baseline verification rerunnable through one CI/local entrypoint with
  fresh build and consumer environments and preserved receipts; document exact
  environment identity and keep consumer checks behind public validation APIs.
- Make every skill folder self-contained with a generated, manifest-derived
  compatibility resource and include all distributed resources in validation
  and consumer receipt identity; advance the root manifest schema to version 2.
- Add deterministic allowlisted portable pack/individual builds, normalized
  archives, checksummed release inventories, cross-platform CI commands,
  installation guidance, and a release-preparation dossier.
- Make compatibility/hash regeneration a validated all-files transaction that
  bootstraps missing generated resources, and add a clean-tree `--frozen`
  package gate for release candidates.
- Harden cross-platform path handling, interrupted-write hygiene, archive
  symlink rejection, and frozen/inventory negative coverage before release
  candidate freeze.
- Add a manually dispatched, read-only Windows/Ubuntu check for the published
  `v0.1.0` asset allowlist, reconstructed package bytes, and disposable full
  plus individual installation.
- Receipt schema 2 replaces the schema-1 `skills` identity with
  `distributed_files` and complete packaging inputs. Schema-1 receipts are
  superseded and cannot be rechecked by this verifier; retain their original
  tool revision or create fresh schema-2 evidence.
