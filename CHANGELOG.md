# Changelog

All notable user-facing changes to RPA Core Agent Skills will be recorded here.

## Unreleased

### Added

- Added the development-only portable repository foundation, seven draft RPA
  Core skills, deterministic compatibility/hash manifest, and static validation.

### Changed

- Align all seven skills and immutable documentation links with released Core
  0.3.0 and its Step API; retain development-only companion status.
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
  installation guidance, and a no-publish support dossier.
- Make compatibility/hash regeneration a validated all-files transaction that
  bootstraps missing generated resources, and add a clean-tree `--frozen`
  package gate for release candidates.
- Receipt schema 2 replaces the schema-1 `skills` identity with
  `distributed_files` and complete packaging inputs. Schema-1 receipts are
  superseded and cannot be rechecked by this verifier; retain their original
  tool revision or create fresh schema-2 evidence.
