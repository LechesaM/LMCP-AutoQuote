# LMCP Command Centre FINAL Frontend

This package is the corrected dark command-centre UI.

Expected heading after start:

- LMCP AutoQuote Command Centre
- Autonomous Tender Control Tower

Start:

```bash
rm -rf node_modules dist .vite
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

Backend must run separately on port 8000:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

If the browser still shows `LMCP Autonomous Tender System`, you are running the old frontend folder.
