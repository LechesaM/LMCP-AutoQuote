# LMCP Core

`lmcp-core/` is the future enterprise platform root for LMCP AutoQuote.

Current purpose:

- define the target platform structure
- separate future platform ownership from the current production runtime
- allow gradual migration without changing current imports or startup paths

Current constraint:

- the existing runtime under the repository root remains authoritative until migration steps explicitly promote code into this tree

