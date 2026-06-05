# Governance Status

Current Certification Status: `APPROVED`

Current Milestone: `Controlled Production Candidate`

Tag: `controlled-production-candidate-2026-06-04`

Last Certified Run:

- Weekly Regression Run #1
- Commit: `cc31c532`

Certified Evidence:

- Baseline #1
- Baseline #2
- Controlled Production Certification
- Weekly Regression Run #1
- CI Gate Validation (`2026-06-04`)
- Submission Centre Refactor Validation (`2026-06-04`)
- Weekly Report Export Validation (`2026-06-05`)

Certified Maintenance Evidence:

- Local startup wiring validation: frontend startup now receives the backend URL started by the local production launcher.
- Weekly report workspace validation: active shared-repo frontend includes the sidebar `Weekly Report` workspace and exports markdown from page state.
- Operator auth endpoint validation: endpoint alive; invalid-password check returned the expected `401`.
- Real login was not performed because the `pilot-admin` password is not documented.
- Controlled proof safety gate passed: controlled status `controlled`, workflow checks `7 / 7`, portal upload blocked, email send blocked, and final submit blocked.

Allowed Changes:

- Bug fixes
- Proof improvements
- Operator documentation
- Small stability patches

Restricted Changes:

- Feature development
- Autonomous submission
- Portal upload enablement
- Email send enablement

Next Scheduled Activity: `Weekly Regression Run #2`

## Operating Posture

- Keep the repository frozen.
- Make no workflow changes.
- Make no policy changes.
- Wait for a valid trigger such as time elapsed, an approved patch, a dependency change, or an environment change.
- Then execute Weekly Regression Run #2 and compare it against Baseline #1, Baseline #2, the Controlled Production Certification, and Weekly Regression Run #1.
- CI gate and refactor validations should be recorded separately as proof improvements and linked from the relevant regression note.
- Weekly report export validation is certified maintenance evidence and should be compared during Weekly Regression Run #2 without treating it as workflow enablement.
