# Nyx umbrella

This repository coordinates the independently released suite. App implementations
live in their own nyx-<app> repositories; shared APIs/assets live in nyx-core and
nyx-design. Use suite.toml and `bin/nyx dev setup` to locate owning checkouts.
This repository holds no app source; the pre-split monorepo is in its history at
suite.toml's `baseline`.

Migration baseline and boundaries: MULTIREPO_MIGRATION.md.
Suite source of truth: suite.toml. Local checkout overrides: ignored .nyx-local.json. Every application repository is
independent; see suite.toml for supported immutable commits and
docs/migration/repositories.json for active local locations.
Common agent rules: docs/AGENTS_COMMON.md. Canonical shared style (STYLE.md) and widgets
are maintained in design-nexus/nyx-design.

Commands: `bin/nyx dev status`, `bin/nyx dev build archive`,
`bin/nyx release check`, `bin/nyx release notes APP`.
Install/update commands consume versioned standalone releases and verify manifest
checksums. Apps without a release install from their repo at the pinned revision; `NYX_BUILD=1`
builds released apps from source.
Run only essential checks for changed packages. Never download models or run
inference for routine verification. Keep identities, application data, and existing
integrations stable. Use public pinned dependencies across repository boundaries.
Install updates without opening/restarting applications. Restarting background services after installation is allowed. The 25 source repositories
have publication approval; new remote repositories still require explicit approval.
