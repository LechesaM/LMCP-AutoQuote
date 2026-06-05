# Win Probability Calibration

This calibration note is advisory-only and compares predicted opportunity scores with actual award outcomes.

## Inputs
- Predicted opportunity score
- Actual award outcome
- Verification status: Award Confirmed, Verified, Derived
- Province coverage
- Category coverage
- Supplier depth

## Calibration Loop
1. Record the predicted score at RFQ review time.
2. Later compare the score against actual award outcome or verified non-award outcome.
3. Track false positives, false negatives, and score drift by province and category.
4. Reweight the advisory model only after evidence review.

## Success Criterion
A calibrated score should improve ranking quality without creating runtime automation or changing submission behavior.
