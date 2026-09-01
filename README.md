# Bhoomi-Rakshak

Early warning and landslide risk monitoring MVP for Northeast India. Current slice: seeded NER zones, the weighted risk engine, live rainfall simulation, and a dashboard consuming the API.

## Run the API

```bash
python -m pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

## Run the dashboard

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` after starting both services.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | /health | Service status |
| GET | /risk-scores | All zones with current score/level |
| POST | /simulate-rainfall | `{zone_id, rainfall_mm}` → recomputed zone risk |
| GET | /alerts | Auto-generated High/Severe alerts, newest first |
