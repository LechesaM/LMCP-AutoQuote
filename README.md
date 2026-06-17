# LMCP

Pilot workspace entrypoints:

- Run one pilot folder:
```bash
python3 scripts/run_workspace_pilot.py \
  --workspace-root /Users/cash/Documents/lmcp_pilot_runs \
  --pilot-id PILOT-001
```

- Run the full pilot batch:
```bash
make pilot-batch
```

- Run a single pilot through the batch wrapper:
```bash
make pilot-batch-one PILOT_ID=PILOT-001
```

- Record explicit operator approval for a workspace folder:
```bash
python3 scripts/approve_workspace_pilot.py \
  --workspace-root /Users/cash/Documents/lmcp_pilot_runs \
  --pilot-id PILOT-002 \
  --confirm-approval
```

Pilot rules:
- Operator approval remains mandatory.
- Do not auto-submit bids.
- Do not auto-send final quotes.
- Do not auto-approve pricing.
