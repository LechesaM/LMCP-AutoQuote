# Ranking Engine Spec (Scale-to-Thousands)

Goal: prioritize RFQs to maximize speed + win probability while staying compliant.

## Output fields (stored on opportunities)
- `priority_score` (float)
- `priority_band` ('A' | 'B' | 'C')
- `score_features` (jsonb): explainability

## Band definitions
- A: auto-process first (high confidence, email allowed, near deadline)
- B: process, but requires human review
- C: archive/ignore or process when capacity allows

## Features (v1 weights)
1) Time-to-close: +18 (<=24h), +12 (<=72h), +6 (<=7d), +2 otherwise
2) Email allowed + response email: +20
3) Portal penalty: -8
4) SOE match bonus: +12 (>=0.85), +6 (>=0.70), +2 (>=0.60)
5) needs_review penalty: -20
6) compliance ready: +10, missing: -5

## v2 learning (when you have outcomes)
Capture:
- tender outcome: won/lost/no_bid
- category
- price competitiveness proxy (if known)
Train simple model:
- logistic regression / gradient boosting
Keep rules as safety rails (email permission, allowlists, MFA gates).
