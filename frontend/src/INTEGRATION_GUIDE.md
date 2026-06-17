# Step 4 Backend Field Mapping

Replace:
- src/services/liveTenderApi.js
- src/services/pipelineActivityApi.js

What this fixes:
- normalizes backend opportunity data into consistent frontend fields
- maps buyer/source/rfq/province/submission method
- infers status when backend uses different field names
- fixes Pipeline Activity counts and status breakdown
- restores source endpoint labels
