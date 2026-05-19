# Pilot Sign-Off SOP

## Purpose
This SOP describes how operators record and review pilot sign-offs during supervised pilot operations.

## Sign-Off Types
- Approval sign-off
- Review sign-off
- Proof sign-off
- Go-live authorization sign-off

## Requirements
- Every sign-off must name the operator.
- No silent approvals are allowed.
- Sign-offs must match the current workflow stage.
- Proof sign-off requires proof-recorded context.
- Final submission sign-offs are not permitted.

## Recording Rules
1. Verify the workflow stage.
2. Confirm the operator identity.
3. Record the sign-off type and note.
4. Persist the sign-off to JSONL and SQLite when available.
5. Preserve the sign-off history for audit review.

## Rejection Rules
- Reject sign-offs that omit the operator.
- Reject sign-offs that attempt to authorize autonomous final submission.
- Reject sign-offs that do not match the required workflow checkpoint.

## Accountability
- The operator remains responsible for the approval decision.
- The sign-off is an explicit human control point, not an automated acknowledgment.

