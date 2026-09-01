# 🛡️ Bhoomi-Rakshak 2.0
### India Multi-Hazard Early Warning & AI Disaster Intelligence System

> *"Predict the cascade. Protect the nation."*

**Bhoomi-Rakshak 2.0** is an operational-grade, AI- and physics-powered multi-hazard early warning, risk forecasting, and disaster intelligence platform designed specifically for high-risk terrains across India — spanning the **Himalayan Belt**, **Western Ghats**, **Northeastern Hills**, and **Coastal Corridors**.

---

## 🌟 Key Highlights & Special Factors

What makes **Bhoomi-Rakshak 2.0** distinct from conventional hazard monitors:

| Innovation | Description |
|---|---|
| **🔬 Dual-Core Hybrid Architecture** | Combines deterministic first-principles geotechnical physics with state-of-the-art ML classifiers to prevent model hallucination and capture physical soil-failure mechanics. |
| **🌪️ 5-Hazard Threat Spectrum** | Simultaneously monitors **Landslides**, **Flash Floods**, **Earthquakes (Co-seismic)**, **Wildfires**, and **Severe Storms/Cyclones**. |
| **🧠 Explainable AI (XAI) Breakdown** | Real-time percentage attribution for every risk score (Slope 30%, 24h Rain 35%, 7d Moisture 20%, Historical Susceptibility 15%) so commanders understand *why* an alert triggered. |
| **🛣️ RoadShield Infrastructure Intelligence** | Directly maps forecasted slope and flood failures to critical **National Highways** (NH766, NH181, NH7, NH544, NH10, etc.) to safeguard supply lines and evacuation routes. |
| **⏱️ 15-Minute Anti-Fatigue Cooldown** | Prevents alert fatigue among first responders by suppressing duplicate warnings for 900 seconds unless risk escalates. |
| **🎯 What-If Multi-Hazard Simulator** | Allows disaster planners and NDRF command teams to inject extreme cloudbursts, M7+ seismic tremors, heatwaves, or cyclone gusts into any target district. |
| **🌐 Trilingual Community Delivery** | Broadcasts alerts in English, Assamese, and Nagamese for regional field adoption. |
| **👥 Rakshak Citizen & Field Crowdsourcing** | Ground incident reporting with auto-verification for field officials and pending triage for citizen submissions. |

---

## 🔬 Scientific & Mathematical Formulation

### 1. Landslide Mechanics (Physics + ML)
- **Infinite Slope Factor of Safety ($FS$)**:
  $$FS = \frac{c' + (\gamma - m\gamma_w) H \cos^2\alpha \tan\phi'}{\gamma H \sin\alpha \cos\alpha}$$
  - $FS > 1.3$: Stable Slope | $1.0 \le FS \le 1.3$: Marginal Stability | $FS < 1.0$: Physical Slope Failure.
- **USGS / IMD Intensity-Duration ($I-D$) Threshold Curve**:
  $$I = 14.82 \cdot D^{-0.39}$$
  Tracks whether 24-hour storm rainfall intensity breaches historical failure thresholds.
- **XGBoost Susceptibility Classifier**: Evaluates slope angle, clay content, hydraulic conductivity ($K_{sat}$), and rainfall history.

### 2. Flash Flood & Runoff (Physics + ML)
- **Rational Method Peak Runoff Discharge ($Q$)**:
  $$Q = \frac{C \cdot I \cdot A}{360} \quad (\text{m}^3/\text{s})$$
- **RandomForest Inundation Regressor**: Predicts expected water depth (meters) based on catchment runoff and terrain slope.

### 3. Wildfire & Dry Fuel Index
- **Chandler Burning Index ($CBI$)**:
  $$CBI = \frac{(110 - 1.373 \cdot RH) \cdot e^{0.0438 \cdot T}}{60} \cdot v$$
  Integrates real-time ambient temperature ($T$), relative humidity ($RH$), and wind velocity ($v$).

### 4. Earthquake & Co-seismic Landslides
- **BIS IS 1893:2016 Seismic Ground Motion**: Integrates Peak Ground Acceleration ($PGA$) and seismic zoning (Zone II to Zone V) to predict co-seismic landslides on steep slopes.

### 5. Evacuation Triage
- **LightGBM Population Classifier**: Prioritizes evacuation urgency based on population density ($D_{pop}$), vulnerable roads, and composite multi-hazard index.

---

## 🗺️ Monitored Districts Matrix (18 High-Risk Districts)

Bhoomi-Rakshak actively tracks 18 critical districts across 10 Indian states:

| District | State | Key Hazard Profiles | Critical Highway |
|---|---|---|---|
| **Wayanad** | Kerala | Severe Landslides, Western Ghats Cloudbursts | **NH766** |
| **Idukki** | Kerala | Mountain Inundation, Slope Instability | **NH85** |
| **Malappuram** | Kerala | Hill Catchment Runoff, Dense Population | **NH966** |
| **Thrissur** | Kerala | Athirapally Catchment, Cyclone Corridor | **NH544** |
| **Nilgiris (Ooty)** | Tamil Nadu | Steepest South Indian Slopes, Landslides | **NH181** |
| **Kanyakumari** | Tamil Nadu | Tri-Ocean Confluence, Coastal Storm Surge | **NH844** |
| **Chamoli** | Uttarakhand | Glacial Lake Outbursts, Co-seismic Rockfalls | **NH7** |
| **Rudraprayag** | Uttarakhand | Cloudbursts, Flash Floods, Kedarnath Route | **NH107** |
| **Shimla** | Himachal Pradesh | Landslides, Soil Creep, Urban Hill Stress | **NH5** |
| **Mandi** | Himachal Pradesh | Beas River Flooding, Slope Slumping | **NH3** |
| **Darjeeling** | West Bengal | Tea Garden Slope Failures, Heavy Monsoons | **NH110** |
| **East Sikkim (Gangtok)** | Sikkim | Teesta Catchment Floods, High Seismicity | **NH10** |
| **East Khasi Hills (Sohra)** | Meghalaya | World's Highest Rainfall Zone, Flash Floods | **NH6** |
| **West Jaintia Hills (Jowai)** | Meghalaya | Heavy Precipitation, Road Cutting Slides | **NH44** |
| **Dima Hasao (Haflong)** | Assam | Barail Range Landslides, Rail Line Severance | **NH27** |
| **Kohima** | Nagaland | Sinking Zones, Mudslides, NH Connectivity | **NH2** |
| **Dimapur** | Nagaland | Plains Flooding, River Inundation | **NH29** |
| **Papum Pare (Itanagar)** | Arunachal Pradesh | Foothill Slope Failures, Heavy Downpours | **NH415** |

---

## 🛠️ Technology Stack

```
┌─────────────────────────────────────────────────────────────┐
│                      FRONTEND LAYER                         │
│  Next.js 15 (App Router) • React 19 • TypeScript            │
│  Leaflet & React-Leaflet • Lucide Icons • CSS3 Custom Props │
└──────────────────────────────┬──────────────────────────────┘
                               │ REST / JSON (15s Polling)
┌──────────────────────────────▼──────────────────────────────┐
│                      BACKEND LAYER                          │
│  FastAPI • Python 3.12 • Uvicorn (ASGI) • SQLite3           │
│  NumPy • Pandas • Scikit-Learn • XGBoost • LightGBM • HTTPX │
└──────────────────────────────┬──────────────────────────────┘
                               │ Telemetry & Geodata
┌──────────────────────────────▼──────────────────────────────┐
│                   DATA & SENSOR FEEDS                       │
│  OpenWeatherMap Live API • ISRO Bhuvan Landslide Inventory  │
│  IMD Monsoon Data (1901-Present) • BIS IS-1893:2016 Seismic │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Getting Started & How to Run

### 1. Prerequisites
- **Python 3.10+** (Python 3.12 recommended)
- **Node.js 18+** & `npm`
- Git

---

### 2. Backend Setup & Launch

1. Open a terminal in the project root directory:
   ```bash
   # Install Python dependencies
   pip install -r backend/requirements.txt
   ```

2. *(Optional)* Set your OpenWeather API Key for live global weather feeds:
   ```powershell
   # On Windows PowerShell:
   $env:OPENWEATHER_API_KEY="your_api_key_here"

   # On Linux / macOS / Bash:
   export OPENWEATHER_API_KEY="your_api_key_here"
   ```

3. Launch the FastAPI server:
   ```bash
   # From workspace root:
   python -m uvicorn backend.main:app --reload --port 8000
   ```
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
