# Sync Branch Policy

The authoritative-state reconciliation branch must be additive and reviewable.

- start from the authoritative local working state;
- use a new `sync/...` branch;
- never force-push `release/v1.1`;
- preserve local history and uncommitted work deliberately;
- review changed paths and secret-sensitive files before publication;
- use a draft PR for reconciliation;
- do not merge until audit and human review complete.
