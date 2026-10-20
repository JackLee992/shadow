# Owned RiskLens laboratory fork

## Branch policy

- `master` mirrors upstream. At verification on 2026-10-20, both masters were
  `9a54ac98a50bc28e0fe7654fa57085a1a8fbcfef`.
- `lab/risklens-main` is the active development baseline, created from that
  latest upstream master. Future lab changes belong here or in topic branches
  based on it, not on the historical release.
- `lab/risklens-ios16-v3.7.6` is a historical compatibility experiment based on
  released v3.7.6 (`edc202054ca70a98eb31c2a141b1b59fd320b59d`). It was selected
  to match the previously installed release, not as the ongoing development
  baseline. Its GitHub comparison reports one documentation commit ahead and
  448 upstream commits behind the verified master. It must not be presented
  as a latest-upstream experiment.

The legacy experiment's local source changes were preserved separately, not
automatically carried forward. New fixes are based on this latest source.

## Scope and acceptance

Keep Shadow reusable for the owner's authorized laboratory projects. Do not
hardcode RiskLens or another special bundle identifier as the fork's allowed
scope. RiskLens is the current experiment's subject, not a product restriction.
Preserve ordinary upstream configuration; do not silently enable all apps.
Preserve upstream attribution and license. Separate source-based hypotheses,
host checks, compiled artifacts and fresh device observations in every report.
An installed package or a written setting does not establish activation.

Inspect the latest source and its declared dependency contract before choosing
a deployment unit. Do not assume a framework from master is interchangeable
with components from v3.7.6. Preserve a complete recoverable original and verify
each trial's final state, including any temporary configuration restoration.
Do not change trust policy or expand the target scope implicitly.

## Public and private material

This is a public fork. Commit only reviewable source, tests and sanitized notes.
Never commit device identifiers, credentials, signing material, private harness
locations, proprietary app artifacts, raw device reports or backups. Follow
`AGENTS.md`; keep private experiment evidence separate from this checkout.
