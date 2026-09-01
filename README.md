# Bhoomi-Rakshak

Bhoomi-Rakshak is a prototype early-warning and monitoring dashboard for landslide and multi-hazard risk across vulnerable districts in India, with a particular focus on the North Eastern Region and other high-risk hill corridors.

This project combines district-level risk scoring, weather adaptation, alert generation, and field reporting into a single demo-ready platform for analysis, simulation, and operational planning.

## What it does

- Tracks multi-hazard district risk using a hybrid scoring model built from terrain, rainfall, historical density, and weather conditions.
- Uses live weather data and a public IMD rainfall feed to adapt risk estimates to current conditions.
- Displays district risk levels and hazard summaries via a dashboard UI.
- Generates warning alerts with language-aware messaging templates.
- Lets citizens and field officials submit incident reports with media attachments.
- Includes a nearest-road geo-match and a response-priority queue based on risk, vulnerability, and road-block status.
- Supports offline queuing for field reports when connectivity is weak or unavailable.

## Included features

- Weather-driven risk calibration
- IMD rainfall augmentation and ingestion contract
- Risk heatmap surface generation
- District severity dashboard with multi-hazard breakdown
- Alert feed and multilingual community messaging templates
- Field report uploads with validation and media retrieval
- Idempotent report retries and offline queue support
- Priority queue for emergency response ordering

## Not included in this version

This repository intentionally focuses on the demo and research features above. It does not include production-grade telecom delivery or cloud deployment setup.

## Project structure

- backend/ — FastAPI API, risk engine, weather integration, report handling, and alerts
- frontend/ — Next.js dashboard UI
- Dockerfile — backend container definition
- frontend/Dockerfile — frontend container definition

## Local setup

### Backend

1. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```

2. Start the API:
   ```bash
   python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
   ```

### Frontend

1. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```

2. Start the dashboard:
   ```bash
   npm run dev
   ```

## Environment

The project uses a local environment file for keys and runtime configuration. Add values as needed for your local environment.

## Validation

The backend test suite is included and can be run with:

```bash
python -m pytest backend/tests -q
```

The frontend can be type-checked with:

```bash
cd frontend
npx tsc --noEmit
```

## Scope note

This is a working prototype for a landslide and multi-hazard monitoring system. It is designed for demonstration, simulation, and research-oriented assessment rather than full-scale production operations. backend.main:app --reload --port 8000   ```
   *The backend API will be live at `http://localhost:8000` (Docs at `http://localhost:8000/docs`).*

---

### 3. Frontend Setup & Launch

1. In a second terminal window, navigate to `frontend/`:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

2. Open **`http://localhost:3000`** (or `http://localhost:3001` if 3000 is occupied) in your browser.

---

### 4. Running Automated Tests & Verification

- **Backend Pytest Suite (29 unit & integration tests)**:
  ```bash
  python -m pytest backend/tests -v
  ```
- **Frontend Type Check**:
  ```bash
  cd frontend
  npx tsc --noEmit
  ```
- **Frontend Production Build**:
  ```bash
  cd frontend
  npm run build
  ```

---

## 📡 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | System health check and metadata. |
| `GET` | `/states` | List of all monitored Indian states. |
| `GET` | `/districts` | Complete district registry with telemetry and hazard coordinates. |
| `GET` | `/risk-scores` | Real-time multi-hazard calculations, physics parameters, and ML scores. |
| `POST` | `/simulate-hazard` | Run what-if simulations on a target district with custom rain, PGA, temp, humidity, and wind. |
| `GET` | `/alerts` | Feed of active `Warning` and `Evacuate` alerts with 15-min cooldown tracking. |
| `GET` | `/reports` | Crowdsourced citizen and verified official field reports. |
| `POST` | `/reports` | Submit ground truth incident reports (GPS tagged with photos). |
| `POST` | `/sync-live-weather` | Trigger manual re-fetch of live weather telemetry. |

---

## 🛡️ Standard 4-Tier Severity Protocol

| Level | Score Range | Meaning & Required Action |
|---|---|---|
| 🟢 **Normal** | `0 – 29` | Slope and terrain within stable physical limits. Routine sensing active. |
| 🟡 **Watch** | `30 – 49` | Elevated moisture or tremor. Pre-position monitoring teams. |
| 🟠 **Warning** | `50 – 74` | High hazard threshold crossed. Restrict civilian movement on mountain highways. |
| 🔴 **Evacuate** | `75 – 100` | Critical failure imminent ($FS < 1.0$ or I-D breached). Immediate evacuation. |

---

## 🤝 Contributing & License
Maintained under the Bhoomi-Rakshak India Disaster Resilience Initiative. All physics models follow ISRO Bhuvan, USGS, and BIS standards.
