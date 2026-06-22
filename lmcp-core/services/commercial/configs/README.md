# Commercial Configs Boundary

This folder is reserved for future commercial-owned static configuration after it can be separated safely from the active runtime.

Target configuration classes:

- pricing policy defaults
- margin and profit thresholds
- supplier adjudication rules
- review and approval gate defaults
- quote-pack generation defaults

Not migrated yet:

- pricing heuristics embedded in live Python modules
- manual review and approval assumptions encoded in runtime services
- lifecycle-linked commercial thresholds embedded in shared orchestration

Current rule:

- no live commercial configuration is moved here until it has no import impact and no runtime path dependency
