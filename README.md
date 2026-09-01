# NER Risk Monitor

Ticket 1 provides the first runnable vertical slice: seeded Northeast India monitoring zones, SQLite persistence, the weighted risk engine, and a dashboard consuming `GET /risk-scores`.

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
