# E2E Validation SOP

## How to Run the RFQ Harness

Run the end-to-end validation harness tests before production use:

```bash
python3 -m pytest tests/test_e2e_rfq_harness.py -q
```

## Fixture Format

Use JSON fixtures with tender metadata, source file references, line items, and expected outcomes.

## Adding Real RFQs

- Add a fixture under `tests/fixtures/rfqs/`
- Include the real source file references
- Keep the fixture aligned with manual-production rules

## Reading the Readiness Report

- Check the pass rate
- Check refusal reasons
- Check persistence verification
- Check audit verification
- Check the manual-production safety status

## Minimum Pass Criteria

- The valid fixture reaches proof-recorded state
- Refusal fixtures are refused for the expected reason
- Persistence and audit verification both succeed
- Manual submission remains preserved

## Validation Frequency

- Run before major changes
- Run after workflow or service consolidation
- Run before a controlled go-live decision

