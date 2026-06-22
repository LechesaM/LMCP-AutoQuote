# Intelligence Configs Boundary

This folder is reserved for future intelligence-owned static configuration after it can be separated safely from the active runtime.

Target configuration classes:

- parser selection and routing rules
- BOQ normalization heuristics
- field mapping and table-detection defaults
- extraction validation thresholds
- handwriting and glyph-processing defaults

Not migrated yet:

- parsing heuristics embedded in live Python modules
- runtime-generated extraction summaries and evidence files
- queue handoff assumptions encoded in lifecycle orchestration

Current rule:

- no live intelligence configuration is moved here until it has no import impact and no runtime path dependency
