# LMCP AutoQuote Branch Management Policy

## Branch Structure

### `release/v1.0`

Purpose:

- Protected production candidate branch containing the validated supervised release.

Permitted Changes:

- Critical bug fixes
- Security fixes
- Operational fixes
- Documentation corrections

Prohibited Changes:

- New features
- New autonomous behaviours
- Workflow redesigns
- Experimental services
- Procurement scope expansion

All changes require review before merge.

### `develop`

Purpose:

- Primary development branch for future releases.

Permitted Changes:

- New features
- `v1.1` enhancements
- Intelligence improvements
- Supplier automation improvements
- Award intelligence enhancements
- Dashboard enhancements

Changes on `develop` must not be merged into `release/v1.0` unless separately approved as a production fix.

### `main`

Purpose:

- Repository integration branch.

Rules:

- Release tags originate from validated release candidates.
- Future release branches are created from validated states.

## Release Protection Rules

The following protections are recommended for `release/v1.0`:

- Require pull request approval
- Require successful CI checks
- Prevent direct pushes
- Require branch protection
- Require signed release tags

## Production Governance

The following settings must remain unchanged in `release/v1.0`:

- Human Approval Required
- Autonomous Final Submission Disabled
- eTenders Guardrails Enabled
- Benchmark Gates Enabled

Any change to these controls requires formal production review and approval.

## Versioning

Current Release:

- `LMCP AutoQuote v1.0`
- Classification: `Production Candidate Release (Supervised)`

Future Development:

- `LMCP AutoQuote v1.1` and later shall be developed exclusively on `develop` until independently validated.
