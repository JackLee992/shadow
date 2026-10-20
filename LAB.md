# Owned RiskLens red-team experiments

This fork preserves the upstream Shadow license and attribution. It is an
independent workspace for authorized experiments against our own RiskLens host,
not a claim that upstream supports or has tested these experiments.

## Branches

- `master`: upstream baseline, kept separate from experiment changes.
- `lab/risklens-ios16-v3.7.6`: starts at upstream `v3.7.6`, commit
  `edc202054ca70a98eb31c2a141b1b59fd320b59d`, to match a reproducible package
  baseline. This branch does not imply compatibility with every current backend.

## Scope and safe defaults

Experiments target only the owned host bundle `com.jacklee.devicerisk.demo`.
Do not enable global defaults or add unrelated applications to an experiment.
Future functional patches belong on experiment branches and must preserve the
upstream default behavior for other hosts.

Installation, effective per-app configuration, installed hooks, native API
effects and SDK outcomes are separate evidence gates. In particular, default
hook-option values or the presence of Shadow classes do not prove that the
per-app `App_Enabled` gate was consumed or that hooks ran.

For each change, retain source and package identities, unmodified controls,
fresh host processes, an independent report check, and an off/on/off recovery
comparison. Honest negative results and residual evasions are valid results;
an in-process fixture is not system-wide hiding evidence.

## Private evidence stays outside this public fork

Do not commit device identifiers, connection profiles, keys, provisioning
profiles, private runtime reports, configuration backups, third-party app
dumps, account material or local absolute paths. Keep those in a separate
private evidence location. This repository contains open-source code and
non-sensitive experiment documentation only.

No release or distribution package has been produced merely by creating this
branch. Experimental packages require their own build, compatibility, native
effect and rollback verification.
