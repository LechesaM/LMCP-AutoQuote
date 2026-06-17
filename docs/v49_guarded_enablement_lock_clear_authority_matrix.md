# V49 Guarded Enablement Lock-Clear Authority Matrix

## Purpose
Define who may clear submission locks, under what conditions, with what approvals, and with what audit requirements before any guarded V49 enablement can be reconsidered.

This is a governance policy artifact, not an implementation change.

## Baseline
- Final submission release control remains `enabled: false`, `stage: "V48"`.
- No runtime change is authorized by this matrix.

## Authority Levels

### 1. Routine Clear
Approved only for narrowly defined operational recovery cases.

Who may clear:
- Designated supervisory operator
- Designated governance reviewer

Conditions:
- Duplicate submission prevention
- Portal synchronization failure recovery
- Corrupted execution state recovery
- Verified failed submission recovery

Requirements:
- Dual approval required
- Reason recorded
- Affected RFQ recorded
- Prior lock state recorded
- Resulting lock state recorded
- Audit event recorded immediately

### 2. Escalated Clear
Used when routine clear is insufficient or when risk is elevated.

Who may clear:
- Senior supervisory operator
- Governance approver

Conditions:
- Emergency rollback
- Recovery from system-wide lock corruption
- Controlled restoration after a confirmed submission workflow fault

Requirements:
- Dual approval required
- Explicit escalation justification required
- Post-action review required
- Immutable governance event required
- Retention of supporting evidence required

### 3. Emergency Override
Emergency override exists only as a governed exception path.

Who may approve:
- Named governance authority

Conditions:
- Severe operational interruption
- Critical recovery where no routine path is safe
- Documented business continuity risk

Requirements:
- Pre-approval where feasible
- Immediate retrospective review if pre-approval is impossible
- Immutable event recording required
- Time-bounded permission only
- Explicit expiration condition required

## Mandatory Audit Fields
Every lock-clear action must capture:
- Operator identity
- Approver identity
- Timestamp
- Affected RFQ
- Prior lock state
- Resulting lock state
- Reason for clear
- Escalation level
- Reference to source evidence
- Retention classification

## Separation of Duties
- The operator requesting a lock clear may not be the sole approver.
- The approver authorizing the clear must be distinct where dual approval is required.
- The reviewer verifying the post-action state must not be the same person who performed the clear when avoidable.

## Immutable Record Requirement
- Every lock-clear action must be recorded as an append-only governance event.
- Corrections must be appended as new events, not written over prior events.
- Any deletion or silent mutation is prohibited.

## Prohibited Uses
Lock clearing must not be used for:
- Convenience overrides
- Queue acceleration
- Validation bypass
- Workaround of missing evidence
- Reuse of a stale or duplicate binder

## Approval Status
- Current status: pending governance approval
- V49 activation dependency: yes

## Sign-Off
- Governance owner:
- Reviewer:
- Date:
- Decision:
- Notes:
