LMCP Restore Pipeline + Apply Pricing V2 Safely

This fixes:
- SyntaxError/IndentationError in app/services/tender_pipeline.py
- Moves Pricing V2 hook away from tender_pipeline.py
- Applies Pricing V2 safely inside full_autonomous_cycle_service.py before force_quote/pipeline call

Run:

cd ~/Downloads
unzip lmcp_restore_pipeline_apply_pricing_v2_safely.zip

cd /Users/Shared/LMCP-AutoQuote-Server

cp ~/Downloads/restore_pipeline_apply_pricing_v2_safely.py .

python3 restore_pipeline_apply_pricing_v2_safely.py

python3 -m py_compile app/services/pricing_engine_v2_realistic.py app/services/tender_pipeline.py app/services/full_autonomous_cycle_service.py app/main.py

docker compose restart api
sleep 8

curl http://localhost:8000/health
curl -X POST http://localhost:8000/full-autonomous-cycle/run
