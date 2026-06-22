# Acquisition Configs Boundary

This folder is reserved for future acquisition-owned static configuration after it can be separated safely from the active runtime.

Target configuration classes:

- source-registry baselines
- portal capability definitions
- fetch-policy defaults
- acquisition retry and backoff policies
- browser and download capture defaults

Not migrated yet:

- source configuration embedded in live Python modules
- environment-driven acquisition toggles
- runtime-generated source packs and health snapshots

Current rule:

- no live acquisition configuration is moved here until it has no import impact and no runtime path dependency
