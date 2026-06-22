# Submission Configs Boundary

This folder is reserved for future submission-owned static configuration after it can be separated safely from the active runtime.

Target configuration classes:

- portal automation defaults
- upload and receipt-capture policies
- submission scheduling and retry thresholds
- submission-pack generation defaults
- controlled-release and proof-capture policies

Not migrated yet:

- portal-flow assumptions embedded in live Python modules
- release gating assumptions coupled to governance services
- runtime-generated proof and submission manifests

Current rule:

- no live submission configuration is moved here until it has no import impact and no runtime path dependency
