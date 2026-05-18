# LMCP Step 2 — Real ON/OFF Backend Wiring

This package gives you the real backend power control and the frontend ON/OFF component.

## Files included

### Backend
- `app/services/system_control_service.py`
- `app/api/system_control.py`

### Frontend
- `frontend/src/services/systemControlApi.js`
- `frontend/src/components/SystemPowerToggle.jsx`

---

## 1) Copy backend files into your project

Copy these into your backend project:
- `app/services/system_control_service.py` -> `YOUR_PROJECT/app/services/system_control_service.py`
- `app/api/system_control.py` -> `YOUR_PROJECT/app/api/system_control.py`

---

## 2) Register the router in `app/main.py`

Add this import near your other router imports:

```python
from app.api.system_control import router as system_control_router
```

Then add this include with your other `app.include_router(...)` lines:

```python
app.include_router(system_control_router)
```

If your project uses a central API router loader, register it there instead.

---

## 3) Copy frontend files

Copy these into your frontend app:
- `frontend/src/services/systemControlApi.js`
- `frontend/src/components/SystemPowerToggle.jsx`

---

## 4) Place the ON/OFF component on your dashboard page

On your dashboard page, import the component:

```jsx
import SystemPowerToggle from './components/SystemPowerToggle';
```

Then place it near the top of the dashboard layout:

```jsx
<SystemPowerToggle />
```

Adjust the import path depending on your page structure.

---

## 5) Frontend env setting

If your frontend runs on Vite, make sure `.env` contains:

```env
VITE_API_BASE_URL=http://localhost:8000
```

---

## 6) Restart services

### Backend
```bash
docker compose restart api
```

### Frontend
```bash
npm run dev
```

---

## 7) Test endpoints directly

### Read status
```bash
curl http://localhost:8000/system-control/status
```

### Turn OFF
```bash
curl -X POST "http://localhost:8000/system-control/off?reason=Manual%20dashboard%20shutdown"
```

### Turn ON
```bash
curl -X POST "http://localhost:8000/system-control/on?reason=Manual%20dashboard%20startup"
```

---

## What OFF does right now

When you switch OFF:
- system state is saved to `runtime/system_control/state.json`
- `runtime/harvester.paused` is created
- harvester/autonomous/submission flags are marked disabled

When you switch ON:
- the pause file is removed
- all flags are marked enabled again

---

## Important note for full 24/7 production control

This is the real control layer for your dashboard, but to make every background process obey the power state, your long-running loops should check:

```python
from app.services.system_control_service import system_is_enabled
```

And stop or skip work whenever `system_is_enabled()` returns `False`.

That is the next hardening step after this package.
