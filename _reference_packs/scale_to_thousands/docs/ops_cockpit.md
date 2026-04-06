# Ops Cockpit (Thousands Mode)

## Must-have dashboards
- RFQs ingested/day
- RFQs processed/day
- Stage backlog counts (ingest/extract/pricing/pack/send)
- Median time: ingest→ready_to_submit
- Blocked send reasons (top 10)
- Extraction confidence histogram
- Worker CPU/memory by pool

## Must-have alerts
- queue depth per stage > threshold
- extraction failures spike
- send failures spike
- API 5xx
- DB storage low
- Redis CPU high
