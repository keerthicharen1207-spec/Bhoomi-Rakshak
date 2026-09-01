"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";

const RiskMap = dynamic(() => import("./RiskMap"), {
  ssr: false,
  loading: () => <div className="map-placeholder">LOADING INDIA DISTRICT TERRAIN MAP…</div>,
});

type PhysicsData = {
  factor_of_safety: number;
  flash_flood_q_m3s: number;
  wildfire_cbi: number;
  wildfire_category: string;
  id_threshold_breached: boolean;
  id_breach_ratio: number;
};

type MLData = {
  landslide_susceptibility: number;
  flood_depth_m: number;
  population_triage_level: string;
};

type LiveWeather = {
  status: string;
  temp_c: number;
  humidity_pct: number;
  wind_kmh: number;
  rainfall_mm: number;
  weather_desc?: string;
};

type DisasterInfo = {
  landslide?: {
    name: string;
    score: number;
    level: string;
    fs: number;
    fs_status: string;
    probability_pct: number;
    id_breached: boolean;
    id_ratio: number;
  };
  flood?: {
    name: string;
    score: number;
    level: string;
    peak_discharge_m3s: number;
    inundation_depth_m: number;
    runoff_status: string;
  };
  wildfire?: {
    name: string;
    score: number;
    level: string;
    cbi_score: number;
    category: string;
    rh_pct: number;
    temp_c: number;
  };
  earthquake?: {
    name: string;
    score: number;
    level: string;
    zone: string;
    zone_factor_z: number;
    category: string;
    pga_g: number;
    coseismic_risk_score: number;
  };
  storm?: {
    name: string;
    score: number;
    level: string;
    category: string;
    wind_kmh: number;
    rain_24h_mm: number;
  };
};

type Zone = {
  id: number;
  name: string;
  state: string;
  lat: number;
  lng: number;
  slope_angle_norm: number;
  historical_density_norm: number;
  pop_density: number;
  rainfall_24h_norm: number;
  rainfall_7d_norm: number;
  risk_score: number;
  risk_level: "Normal" | "Watch" | "Warning" | "Evacuate";
  physics?: PhysicsData;
  ml?: MLData;
  disasters?: DisasterInfo;
  live_weather?: LiveWeather;
};

type AlertMessages = {
  authority: string;
  community: { en: string; as: string; nl: string };
};

type Alert = {
  id: number;
  zone_id: number;
  zone_name: string;
  zone_state: string;
  level: "Warning" | "Evacuate" | "High" | "Severe";
  messages: AlertMessages;
  created_at: string;
};

type Report = {
  id: number;
  lat: number;
  lng: number;
  description: string;
  photo_url: string;
  source: "citizen" | "field_official";
  status: "pending" | "verified";
  created_at: string;
};

type SimulationResult = { text: string; level: string };

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const RAINFALL_MAX_MM = 200;

const PRESETS = [
  { label: "10MM DRIZZLE", mm: 10 },
  { label: "60MM SHOWER", mm: 60 },
  { label: "120MM DOWNPOUR", mm: 120 },
  { label: "200MM EXTREME", mm: 200 },
];

const LANGUAGES = [
  { code: "en", label: "ENGLISH" },
  { code: "as", label: "অসমীয়া" },
  { code: "nl", label: "NAGAMESE" },
] as const;

type LanguageCode = (typeof LANGUAGES)[number]["code"];

function rainfallBand(mm: number): string {
  if (mm < 15) return "LIGHT";
  if (mm < 65) return "MODERATE";
  if (mm < 115) return "HEAVY";
  return "VERY HEAVY";
}

function alertTime(alert: Alert): string {
  return new Date(alert.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function reportTime(report: Report): string {
  return new Date(report.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function Dashboard() {
  const [zones, setZones] = useState<Zone[]>([]);
  const [allZones, setAllZones] = useState<Zone[]>([]);
  const [states, setStates] = useState<string[]>([]);
  const [selectedState, setSelectedState] = useState<string>("ALL STATES");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState("—");
  const [selectedZoneId, setSelectedZoneId] = useState<number | null>(null);
  const [rainfallMm, setRainfallMm] = useState(60);
  const [simulating, setSimulating] = useState(false);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [language, setLanguage] = useState<LanguageCode>("en");

  const [reports, setReports] = useState<Report[]>([]);
  const [reportLat, setReportLat] = useState("25.27");
  const [reportLng, setReportLng] = useState("91.73");
  const [reportDescription, setReportDescription] = useState("");
  const [reportPhotoUrl, setReportPhotoUrl] = useState("");
  const [reportSource, setReportSource] = useState<"citizen" | "field_official">("citizen");
  const [submittingReport, setSubmittingReport] = useState(false);
  const [reportResult, setReportResult] = useState<{ text: string; error?: boolean } | null>(null);
  const [activeDisaster, setActiveDisaster] = useState<"landslide" | "flood" | "earthquake" | "wildfire" | "storm">("landslide");

  const loadZones = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/districts`);
      if (!response.ok) throw new Error("Risk service unavailable");
      const data: Zone[] = await response.json();
      setAllZones(data);
      setError(null);
      setSelectedZoneId((current) => current);
      setUpdatedAt(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    } catch {
      setError("Could not connect to the risk engine. Start the API on port 8000.");
    }
  }, []);

  const loadStates = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/states`);
      if (!response.ok) return;
      const data: string[] = await response.json();
      setStates(data);
    } catch {
      // silently fail
    }
  }, []);

  const loadAlerts = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/alerts`);
      if (!response.ok) throw new Error("Alert feed unavailable");
      setAlerts(await response.json());
    } catch {
      // Keep existing alerts if offline
    }
  }, []);

  const loadReports = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/reports`);
      if (!response.ok) throw new Error("Reports feed unavailable");
      setReports(await response.json());
    } catch {
      // Keep existing reports if offline
    }
  }, []);

  // Client-side filter: state + search
  useEffect(() => {
    let filtered = allZones;
    if (selectedState !== "ALL STATES") {
      filtered = filtered.filter((z) => z.state === selectedState);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (z) =>
          z.name.toLowerCase().includes(q) ||
          (z.state ?? "").toLowerCase().includes(q)
      );
    }
    setZones(filtered);
  }, [allZones, selectedState, searchQuery]);

  useEffect(() => {
    loadZones();
    loadStates();
    loadAlerts();
    loadReports();
    const interval = setInterval(() => {
      loadZones();
      loadAlerts();
      loadReports();
    }, 15000);
    return () => clearInterval(interval);
  }, [loadZones, loadStates, loadAlerts, loadReports]);

  const handleLocationSelect = useCallback((lat: number, lng: number) => {
    setReportLat(lat.toFixed(2));
    setReportLng(lng.toFixed(2));
  }, []);

  const handleSelectZone = useCallback((id: number) => {
    setSelectedZoneId(id);
  }, []);

  async function runSimulation() {
    if (selectedZoneId === null) return;
    setSimulating(true);
    setResult(null);
    try {
      const response = await fetch(`${API_URL}/simulate-rainfall`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ zone_id: selectedZoneId, rainfall_mm: rainfallMm }),
      });
      if (!response.ok) throw new Error("Simulation failed");
      const updated: Zone = await response.json();
      await loadZones();
      await loadAlerts();
      setResult({
        text: `${updated.name.toUpperCase()} (${updated.state?.toUpperCase() ?? "INDIA"}) → ${updated.risk_level.toUpperCase()} · SCORE ${updated.risk_score.toFixed(1)}`,
        level: updated.risk_level.toLowerCase(),
      });
    } catch {
      setResult({ text: "SIMULATION FAILED — IS THE RISK ENGINE RUNNING?", level: "error" });
    } finally {
      setSimulating(false);
    }
  }

  async function submitReport(event: React.FormEvent) {
    event.preventDefault();
    if (!reportDescription.trim()) return;
    setSubmittingReport(true);
    setReportResult(null);
    try {
      const response = await fetch(`${API_URL}/reports`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lat: parseFloat(reportLat),
          lng: parseFloat(reportLng),
          description: reportDescription.trim(),
          photo_url: reportPhotoUrl.trim(),
          source: reportSource,
        }),
      });
      if (!response.ok) throw new Error("Submission failed");
      const created: Report = await response.json();
      setReportDescription("");
      setReportPhotoUrl("");
      await loadReports();
      setReportResult({
        text: `REPORT SUBMITTED · STATUS: ${created.status.toUpperCase()}`,
      });
    } catch {
      setReportResult({ text: "SUBMISSION FAILED", error: true });
    } finally {
      setSubmittingReport(false);
    }
  }

  const evacuateCount = allZones.filter((z) => z.risk_level === "Evacuate" || (z.risk_level as string) === "Severe").length;
  const warningCount = allZones.filter((z) => z.risk_level === "Warning" || (z.risk_level as string) === "High").length;
  const sliderPercent = (rainfallMm / RAINFALL_MAX_MM) * 100;
  const latestAlert = alerts[0] ?? null;

  // Selected district for the full-fledged summary card
  const selectedDistrict: Zone | null =
    selectedZoneId !== null ? (allZones.find((z) => z.id === selectedZoneId) ?? null) : null;

  return (
    <main>
      <header className="topbar">
        <div className="brand-mark">NER<span>•</span></div>
        <div className="topbar-meta">INDIA DISTRICT MULTI-HAZARD MONITOR <b>● LIVE</b></div>
      </header>
      <section className="hero">
        <div>
          <p className="eyebrow">ALL INDIA / DISTRICT-LEVEL FIELD VIEW</p>
          <h1>Know the slope<br /><em>before it moves.</em></h1>
          <p className="lede">Live multi-hazard monitoring across India covering Landslide, Flash Flood, Earthquake, Wildfire &amp; Storm risks with Physics equations &amp; ML models.</p>
        </div>
        <div className="timestamp">LAST UPDATED<br /><strong>{updatedAt}</strong></div>
      </section>
      <section className="summary">
        <div><span>DISTRICTS MONITORED</span><strong>{allZones.length || "—"}</strong></div>
        <div><span>WARNING TIER</span><strong className="amber">{warningCount || "—"}</strong></div>
        <div><span>EVACUATE TIER</span><strong className="red">{evacuateCount || "—"}</strong></div>
        <div className="summary-note">Hybrid Physics (FS, Q, CBI, IS-1893) &amp;<br />ML (XGBoost, RandomForest, LightGBM).</div>
      </section>

      {/* ── State Filter + Search Bar ── */}
      <section className="filter-bar" style={{ padding: "12px 40px", display: "flex", gap: "12px", alignItems: "center", background: "#f4f6f4", borderBottom: "1px solid #dde4d8", flexWrap: "wrap" }}>
        <span style={{ fontSize: "10px", fontWeight: 700, color: "#465551", letterSpacing: "0.08em" }}>FILTER BY STATE:</span>
        <select
          value={selectedState}
          onChange={(e) => setSelectedState(e.target.value)}
          style={{ fontSize: "12px", padding: "6px 10px", border: "1px solid #c8d4c5", borderRadius: "4px", background: "#fff", color: "#182322", cursor: "pointer" }}
        >
          <option value="ALL STATES">ALL STATES ({allZones.length})</option>
          {states.map((s) => (
            <option key={s} value={s}>
              {s} ({allZones.filter((z) => z.state === s).length})
            </option>
          ))}
        </select>
        <span style={{ fontSize: "10px", fontWeight: 700, color: "#465551", letterSpacing: "0.08em", marginLeft: "8px" }}>SEARCH:</span>
        <input
          type="text"
          placeholder="Search district or state…"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{ fontSize: "12px", padding: "6px 10px", border: "1px solid #c8d4c5", borderRadius: "4px", background: "#fff", color: "#182322", minWidth: "200px" }}
        />
        {(selectedState !== "ALL STATES" || searchQuery) && (
          <button
            type="button"
            onClick={() => { setSelectedState("ALL STATES"); setSearchQuery(""); }}
            style={{ fontSize: "10px", padding: "5px 10px", border: "1px solid #c8d4c5", borderRadius: "4px", background: "#fff", color: "#71807c", cursor: "pointer" }}
          >
            CLEAR ×
          </button>
        )}
        <span style={{ marginLeft: "auto", fontSize: "11px", color: "#71807c" }}>
          Showing <strong>{zones.length}</strong> of <strong>{allZones.length}</strong> districts
        </span>
      </section>

      {/* ── Geospatial Map View ── */}
      <section className="map-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">INDIA DISTRICT GEOSPATIAL VIEW</p>
            <h2>District Risk Map</h2>
          </div>
          <div className="legend">
            <span className="dot normal" />NORMAL
            <span className="dot watch" />WATCH
            <span className="dot warning" />WARNING
            <span className="dot evacuate" />EVACUATE
            <span className="dot-report verified" />VERIFIED REPORT
            <span className="dot-report pending" />PENDING
          </div>
        </div>
        <RiskMap
          zones={zones}
          reports={reports}
          selectedZoneId={selectedZoneId}
          onSelectZone={handleSelectZone}
          onLocationSelect={handleLocationSelect}
        />
      </section>

      {/* ── District Command Center & Disaster Intelligence ── */}
      <section className="content">
        <div className="section-heading">
          <div>
            <p className="eyebrow">DISTRICT COMMAND CENTER</p>
            <h2>Multi-Hazard Intelligence &amp; Simulation</h2>
          </div>
          <p className="sim-note">SELECT ANY DISTRICT TO INSPECT ITS COMPLETE MULTI-DISASTER PROFILE</p>
        </div>

        {/* Rainfall Simulator Tool */}
        <div className="simulator">
          <div className="sim-head">
            <p className="eyebrow">RAINFALL SIMULATOR</p>
            <p className="sim-note">SIMULATED FEED — DRIVES PHYSICS (FS, Q) &amp; ML INFERENCE DIRECTLY</p>
          </div>
          <div className="sim-controls">
            <label className="sim-field">
              <span>TARGET DISTRICT</span>
              <select
                value={selectedZoneId ?? allZones[0]?.id ?? ""}
                onChange={(event) => setSelectedZoneId(Number(event.target.value))}
                disabled={allZones.length === 0}
              >
                {allZones.map((zone) => (
                  <option key={zone.id} value={zone.id}>
                    {zone.name.toUpperCase()} · {zone.state.toUpperCase()}
                  </option>
                ))}
              </select>
            </label>
            <label className="sim-field">
              <span>
                24H RAINFALL <b>{rainfallMm}MM · {rainfallBand(rainfallMm)}</b>
              </span>
              <input
                type="range"
                min={0}
                max={RAINFALL_MAX_MM}
                step={5}
                value={rainfallMm}
                onChange={(event) => setRainfallMm(Number(event.target.value))}
                style={{
                  background: `linear-gradient(to right, #182322 ${sliderPercent}%, #edf1eb ${sliderPercent}%)`,
                }}
              />
            </label>
            <button
              type="button"
              className="run"
              onClick={runSimulation}
              disabled={simulating || selectedZoneId === null}
            >
              {simulating ? "SIMULATING…" : "RUN SIMULATION →"}
            </button>
            <div className="sim-presets">
              {PRESETS.map((preset) => (
                <button
                  key={preset.mm}
                  type="button"
                  className={rainfallMm === preset.mm ? "chip active" : "chip"}
                  onClick={() => setRainfallMm(preset.mm)}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>
          {result && <p className={`sim-result ${result.level}`}>{result.text}</p>}
        </div>


        {error ? (
          <div className="error">{error}</div>
        ) : selectedDistrict ? (
          /* ── Full-Fledged District Summary Command Card ── */
          <div className="district-summary-card">
            <div className={`risk-strip ${selectedDistrict.risk_level.toLowerCase()}`} />

            {/* Header / Hero Bar */}
            <div className="district-hero-bar">
              <div className="district-title-group">
                <h2>{selectedDistrict.name}</h2>
                <div className="district-meta-tags">
                  <span className="state-badge">{selectedDistrict.state.toUpperCase()}</span>
                  <span className="coord-badge">
                    {selectedDistrict.lat.toFixed(2)}°N / {selectedDistrict.lng.toFixed(2)}°E (India)
                  </span>
                  <span className="pop-badge">
                    POPULATION DENSITY: <b>{Math.round(selectedDistrict.pop_density)} / km²</b>
                  </span>
                </div>
              </div>
              <div className="district-score-display">
                <div className="score-box">
                  <div className="main-val">{selectedDistrict.risk_score.toFixed(1)}</div>
                  <span className="score-label">OVERALL MULTI-HAZARD RISK (/100)</span>
                </div>
                <span className={`risk-pill-large ${selectedDistrict.risk_level.toLowerCase()}`}>
                  {selectedDistrict.risk_level} RISK
                </span>
              </div>
            </div>

            {/* Live Meteorological Observations Banner */}
            <div className="live-weather-banner">
              <span className="weather-tag">LIVE WEATHER</span>
              <span className="weather-item">
                TEMPERATURE: <b>{selectedDistrict.live_weather?.temp_c ?? 24}°C</b>
              </span>
              <span className="weather-item">
                HUMIDITY: <b>{selectedDistrict.live_weather?.humidity_pct ?? 75}%</b>
              </span>
              <span className="weather-item">
                WIND SPEED: <b>{selectedDistrict.live_weather?.wind_kmh ?? 12} km/h</b>
              </span>
              <span className="weather-item">
                OBSERVED RAIN: <b>{selectedDistrict.live_weather?.rainfall_mm ?? 15} mm</b>
              </span>
              <span className="weather-item">
                CONDITION: <b>{selectedDistrict.live_weather?.weather_desc?.toUpperCase() ?? "CLOUDY"}</b>
              </span>
            </div>

            {/* Explainable AI (XAI) Risk Driver Breakdown Banner */}
            {(() => {
              const slopeContrib = 0.30 * selectedDistrict.slope_angle_norm;
              const rain24Contrib = 0.35 * selectedDistrict.rainfall_24h_norm;
              const rain7dContrib = 0.20 * selectedDistrict.rainfall_7d_norm;
              const histContrib = 0.15 * selectedDistrict.historical_density_norm;
              const totalContrib = (slopeContrib + rain24Contrib + rain7dContrib + histContrib) || 1;
              const slopePct = Math.round((slopeContrib / totalContrib) * 100);
              const rain24Pct = Math.round((rain24Contrib / totalContrib) * 100);
              const rain7dPct = Math.round((rain7dContrib / totalContrib) * 100);
              const histPct = Math.max(0, 100 - slopePct - rain24Pct - rain7dPct);

              return (
                <div style={{ padding: "12px 32px", background: "#f8faf7", borderBottom: "1px solid var(--line)", display: "flex", gap: "16px", alignItems: "center", flexWrap: "wrap", fontSize: "11px", fontFamily: "'DM Mono', monospace" }}>
                  <span style={{ background: "#182322", color: "#fff", fontWeight: 700, fontSize: "9px", padding: "3px 8px", borderRadius: "2px", letterSpacing: "1px" }}>🧠 XAI RISK DRIVERS</span>
                  <span style={{ color: "#3f534e" }}>
                    Terrain Slope (30% wt): <b style={{ color: "#182322" }}>{slopePct}%</b>
                  </span>
                  <span style={{ color: "#c8d4c5" }}>•</span>
                  <span style={{ color: "#3f534e" }}>
                    24h Rainfall (35% wt): <b style={{ color: "#182322" }}>{rain24Pct}%</b>
                  </span>
                  <span style={{ color: "#c8d4c5" }}>•</span>
                  <span style={{ color: "#3f534e" }}>
                    7d Antecedent Rain (20% wt): <b style={{ color: "#182322" }}>{rain7dPct}%</b>
                  </span>
                  <span style={{ color: "#c8d4c5" }}>•</span>
                  <span style={{ color: "#3f534e" }}>
                    Historical Density (15% wt): <b style={{ color: "#182322" }}>{histPct}%</b>
                  </span>
                </div>
              );
            })()}

            {/* 5 Multi-Hazard Disaster Spectrum Cards */}
            <div className="disaster-spectrum-section">
              <div className="spectrum-heading">
                <span>Multi-Disaster Threat Spectrum</span>
                <span>Physics Equations &amp; Machine Learning Engine</span>
              </div>
              <div className="disaster-toggles" style={{ display: "flex", gap: "8px", margin: "12px 0", flexWrap: "wrap" }}>
                <button type="button" className={`chip ${activeDisaster === "landslide" ? "active" : ""}`} onClick={() => setActiveDisaster("landslide")}>🏔️ Landslide</button>
                <button type="button" className={`chip ${activeDisaster === "flood" ? "active" : ""}`} onClick={() => setActiveDisaster("flood")}>🌊 Flood</button>
                <button type="button" className={`chip ${activeDisaster === "earthquake" ? "active" : ""}`} onClick={() => setActiveDisaster("earthquake")}>⚡ Earthquake</button>
                <button type="button" className={`chip ${activeDisaster === "wildfire" ? "active" : ""}`} onClick={() => setActiveDisaster("wildfire")}>🔥 Wildfire</button>
                <button type="button" className={`chip ${activeDisaster === "storm" ? "active" : ""}`} onClick={() => setActiveDisaster("storm")}>🌀 Storm</button>
              </div>
              <div className="disaster-grid">
                {/* 1. Landslide Risk */}
                {activeDisaster === "landslide" && (
                <div className="disaster-card landslide">
                  <div>
                    <div className="disaster-header">
                      <span className="disaster-title">🏔️ Landslide &amp; Slope Failure</span>
                      <span className={`disaster-badge ${selectedDistrict.disasters?.landslide?.level.toLowerCase() ?? selectedDistrict.risk_level.toLowerCase()}`}>
                        {selectedDistrict.disasters?.landslide?.level ?? selectedDistrict.risk_level}
                      </span>
                    </div>
                    <div className="disaster-metrics">
                      <div className="disaster-metric-row">
                        <span>Factor of Safety (FS):</span>
                        <b className={selectedDistrict.physics && selectedDistrict.physics.factor_of_safety < 1.0 ? "highlight-alert" : "highlight-ok"}>
                          {selectedDistrict.physics?.factor_of_safety.toFixed(2) ?? "1.10"}
                        </b>
                      </div>
                      <div className="disaster-metric-row">
                        <span>Slope Stability:</span>
                        <b>{selectedDistrict.disasters?.landslide?.fs_status ?? (selectedDistrict.physics && selectedDistrict.physics.factor_of_safety < 1.0 ? "Unstable" : "Marginally Stable")}</b>
                      </div>
                      <div className="disaster-metric-row">
                        <span>ML Landslide Probability:</span>
                        <b>{Math.round((selectedDistrict.ml?.landslide_susceptibility ?? 0.75) * 100)}%</b>
                      </div>
                      <div className="disaster-metric-row">
                        <span>USGS I-D Threshold:</span>
                        <b className={selectedDistrict.physics?.id_threshold_breached ? "highlight-alert" : "highlight-ok"}>
                          {selectedDistrict.physics?.id_threshold_breached ? "BREACHED" : "SAFE"}
                        </b>
                      </div>
                    </div>
                  </div>
                  <div className="disaster-progress">
                    <div
                      className="disaster-progress-bar"
                      style={{
                        width: `${Math.min(100, Math.round((selectedDistrict.ml?.landslide_susceptibility ?? 0.75) * 100))}%`,
                        background: (selectedDistrict.ml?.landslide_susceptibility ?? 0.75) > 0.7 ? "#df6651" : "#ecad4b",
                      }}
                    />
                  </div>
                </div>
                )}

                {/* 2. Flash Flood & Inundation */}
                {activeDisaster === "flood" && (
                <div className="disaster-card flood">
                  <div>
                    <div className="disaster-header">
                      <span className="disaster-title">🌊 Flash Flood &amp; Inundation</span>
                      <span className={`disaster-badge ${selectedDistrict.disasters?.flood?.level.toLowerCase() ?? "medium"}`}>
                        {selectedDistrict.disasters?.flood?.level ?? "MEDIUM"}
                      </span>
                    </div>
                    <div className="disaster-metrics">
                      <div className="disaster-metric-row">
                        <span>Peak Discharge (Q):</span>
                        <b>{selectedDistrict.physics?.flash_flood_q_m3s ?? 8.5} m³/s</b>
                      </div>
                      <div className="disaster-metric-row">
                        <span>ML Flood Inundation Depth:</span>
                        <b>{selectedDistrict.ml?.flood_depth_m.toFixed(2) ?? "0.80"} m</b>
                      </div>
                      <div className="disaster-metric-row">
                        <span>Runoff Status:</span>
                        <b>{selectedDistrict.disasters?.flood?.runoff_status ?? "Elevated Runoff"}</b>
                      </div>
                      <div className="disaster-metric-row">
                        <span>Rational Catchment Area:</span>
                        <b>250 Hectares</b>
                      </div>
                    </div>
                  </div>
                  <div className="disaster-progress">
                    <div
                      className="disaster-progress-bar"
                      style={{
                        width: `${Math.min(100, Math.round(((selectedDistrict.ml?.flood_depth_m ?? 0.8) / 2.5) * 100))}%`,
                        background: "#326e8a",
                      }}
                    />
                  </div>
                </div>
                )}

                {/* 3. Seismic Hazard */}
                {activeDisaster === "earthquake" && (
                <div className="disaster-card earthquake">
                  <div>
                    <div className="disaster-header">
                      <span className="disaster-title">⚡ Seismic Vulnerability</span>
                      <span className={`disaster-badge ${selectedDistrict.disasters?.earthquake?.level.toLowerCase() ?? "high"}`}>
                        {selectedDistrict.disasters?.earthquake?.zone ?? "ZONE V"}
                      </span>
                    </div>
                    <div className="disaster-metrics">
                      <div className="disaster-metric-row">
                        <span>IS 1893:2016 Zone:</span>
                        <b>{selectedDistrict.disasters?.earthquake?.zone ?? "ZONE V (High)"}</b>
                      </div>
                      <div className="disaster-metric-row">
                        <span>Peak Ground Acc. (PGA):</span>
                        <b>{selectedDistrict.disasters?.earthquake?.pga_g ?? 0.36} g</b>
                      </div>
                      <div className="disaster-metric-row">
                        <span>Co-Seismic Slope Failure:</span>
                        <b className={(selectedDistrict.disasters?.earthquake?.coseismic_risk_score ?? 0) > 60 ? "highlight-alert" : ""}>
                          {Math.round(selectedDistrict.disasters?.earthquake?.coseismic_risk_score ?? 75)}% Risk
                        </b>
                      </div>
                      <div className="disaster-metric-row">
                        <span>Historical Stress:</span>
                        <b>Very High</b>
                      </div>
                    </div>
                  </div>
                  <div className="disaster-progress">
                    <div
                      className="disaster-progress-bar"
                      style={{
                        width: `${Math.min(100, Math.round(selectedDistrict.disasters?.earthquake?.score ?? 85))}%`,
                        background: "#823f3f",
                      }}
                    />
                  </div>
                </div>
                )}

                {/* 4. Wildfire Risk */}
                {activeDisaster === "wildfire" && (
                <div className="disaster-card wildfire">
                  <div>
                    <div className="disaster-header">
                      <span className="disaster-title">🔥 Wildfire Risk</span>
                      <span className={`disaster-badge ${selectedDistrict.disasters?.wildfire?.level.toLowerCase() ?? "low"}`}>
                        {selectedDistrict.disasters?.wildfire?.level ?? "LOW"}
                      </span>
                    </div>
                    <div className="disaster-metrics">
                      <div className="disaster-metric-row">
                        <span>Chandler Burn Index (CBI):</span>
                        <b>{Math.round(selectedDistrict.physics?.wildfire_cbi ?? 15)} / 100</b>
                      </div>
                      <div className="disaster-metric-row">
                        <span>Vegetation Stress:</span>
                        <b>{selectedDistrict.disasters?.wildfire?.category ?? "Low Spread"}</b>
                      </div>
                      <div className="disaster-metric-row">
                        <span>Temp / Humidity:</span>
                        <b>{selectedDistrict.live_weather?.temp_c ?? 24}°C / {selectedDistrict.live_weather?.humidity_pct ?? 75}%</b>
                      </div>
                    </div>
                  </div>
                  <div className="disaster-progress">
                    <div
                      className="disaster-progress-bar"
                      style={{
                        width: `${Math.min(100, Math.round(selectedDistrict.physics?.wildfire_cbi ?? 15))}%`,
                        background: "#c85523",
                      }}
                    />
                  </div>
                </div>
                )}

                {/* 5. Severe Storm Risk */}
                {activeDisaster === "storm" && (
                <div className="disaster-card storm">
                  <div>
                    <div className="disaster-header">
                      <span className="disaster-title">🌀 Storm &amp; High Wind</span>
                      <span className={`disaster-badge ${selectedDistrict.disasters?.storm?.level.toLowerCase() ?? "low"}`}>
                        {selectedDistrict.disasters?.storm?.level ?? "LOW"}
                      </span>
                    </div>
                    <div className="disaster-metrics">
                      <div className="disaster-metric-row">
                        <span>Wind Velocity:</span>
                        <b>{selectedDistrict.live_weather?.wind_kmh ?? 12} km/h</b>
                      </div>
                      <div className="disaster-metric-row">
                        <span>24h Rain Pressure Load:</span>
                        <b>{Math.round(selectedDistrict.rainfall_24h_norm * 100)}% ({Math.round(selectedDistrict.rainfall_24h_norm * RAINFALL_MAX_MM)} mm)</b>
                      </div>
                      <div className="disaster-metric-row">
                        <span>Storm Advisory Level:</span>
                        <b>{selectedDistrict.disasters?.storm?.category ?? "Normal Breeze"}</b>
                      </div>
                      <div className="disaster-metric-row">
                        <span>Dynamic Wind Pressure:</span>
                        <b>{(0.5 * 1.225 * Math.pow(((selectedDistrict.live_weather?.wind_kmh ?? 12) * 1000) / 3600, 2)).toFixed(1)} N/m²</b>
                      </div>
                    </div>
                  </div>
                  <div className="disaster-progress">
                    <div
                      className="disaster-progress-bar"
                      style={{
                        width: `${Math.min(100, Math.round(selectedDistrict.disasters?.storm?.score ?? 20))}%`,
                        background: "#50328a",
                      }}
                    />
                  </div>
                </div>
                )}
              </div>
            </div>

            {/* Dual Engine: Geotechnical Equations vs AI Projections */}
            <div className="dual-engine-section">
              <div className="engine-box">
                <h4>📐 GEOTECHNICAL &amp; PHYSICAL EQUATIONS</h4>
                <table className="engine-table">
                  <tbody>
                    <tr>
                      <td>Slope Gradient Angle:</td>
                      <td><b>{(selectedDistrict.slope_angle_norm * 45).toFixed(1)}° ({Math.round(selectedDistrict.slope_angle_norm * 100)}% Grade)</b></td>
                    </tr>
                    <tr>
                      <td>Infinite Slope Factor of Safety:</td>
                      <td><b>{selectedDistrict.physics?.factor_of_safety.toFixed(2) ?? "1.14"}</b></td>
                    </tr>
                    <tr>
                      <td>Peak Discharge Runoff Q (Rational):</td>
                      <td><b>{selectedDistrict.physics?.flash_flood_q_m3s ?? 1.13} m³/s</b></td>
                    </tr>
                    <tr>
                      <td>USGS I-D Rainfall Threshold Ratio:</td>
                      <td><b>{selectedDistrict.physics?.id_breach_ratio.toFixed(2) ?? "0.65"}x critical</b></td>
                    </tr>
                    <tr>
                      <td>Chandler Burning Index (CBI):</td>
                      <td><b>{selectedDistrict.physics?.wildfire_cbi ?? 0.0} ({selectedDistrict.physics?.wildfire_category ?? "Low"})</b></td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div className="engine-box">
                <h4>🤖 MACHINE LEARNING INFERENCE MODELS</h4>
                <table className="engine-table">
                  <tbody>
                    <tr>
                      <td>Landslide Susceptibility (XGBoost):</td>
                      <td><b>{((selectedDistrict.ml?.landslide_susceptibility ?? 0.8) * 100).toFixed(1)}% Probability</b></td>
                    </tr>
                    <tr>
                      <td>Flood Inundation Depth (RandomForest):</td>
                      <td><b>{selectedDistrict.ml?.flood_depth_m.toFixed(2) ?? "0.64"} meters</b></td>
                    </tr>
                    <tr>
                      <td>Evacuation Triage Level (LightGBM):</td>
                      <td><b style={{ color: selectedDistrict.ml?.population_triage_level === "Immediate" ? "#9b3626" : "#a36c1e" }}>{selectedDistrict.ml?.population_triage_level ?? "Moderate"}</b></td>
                    </tr>
                    <tr>
                      <td>Historical Hazard Density Weight:</td>
                      <td><b>{Math.round(selectedDistrict.historical_density_norm * 100)}% Historic Index</b></td>
                    </tr>
                    <tr>
                      <td>7-Day Antecedent Moisture Baseline:</td>
                      <td><b>{Math.round(selectedDistrict.rainfall_7d_norm * 100)}% Soil Saturation</b></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        ) : null}
      </section>

      {/* ── Threshold Crossing Alerts Feed ── */}
      <section className="alerts">
        <div className="section-heading">
          <div><p className="eyebrow">ALERT FEED</p><h2>Threshold crossings</h2></div>
          <p className="sim-note">AUTO-GENERATED ON ESCALATION INTO HIGH / SEVERE</p>
        </div>
        <div className="alerts-layout">
          <div className="alert-list">
            {alerts.length === 0 ? (
              <div className="alert-empty">NO ALERTS ISSUED — ALL DISTRICTS BELOW THE WARNING THRESHOLD</div>
            ) : (
              alerts.map((alert) => (
                <article className={`alert-item ${alert.level.toLowerCase()}`} key={alert.id}>
                  <div className="alert-meta">
                    <span className={`level-tag ${alert.level.toLowerCase()}`}>{alert.level.toUpperCase()}</span>
                    <span>{alert.zone_name.toUpperCase()}</span>
                    {alert.zone_state && <span style={{ fontSize: "9px", color: "#71807c" }}>{alert.zone_state}</span>}
                    <span>{alertTime(alert)}</span>
                  </div>
                  <p>{alert.messages.authority}</p>
                </article>
              ))
            )}
          </div>
          <div className="sms-mock">
            <div className="sim-head"><p className="eyebrow">COMMUNITY SMS</p><p className="sim-note">MOCKED VIEW — NO REAL DELIVERY</p></div>
            <div className="lang-toggle">{LANGUAGES.map((lang) => <button key={lang.code} type="button" className={language === lang.code ? "chip active" : "chip"} onClick={() => setLanguage(lang.code)}>{lang.label}</button>)}</div>
            <div className="phone">
              {latestAlert ? (
                <>
                  <p className="phone-to">TO: SUBSCRIBERS — {latestAlert.zone_name.toUpperCase()}{latestAlert.zone_state ? ` · ${latestAlert.zone_state.toUpperCase()}` : ""}</p>
                  <div className="phone-bubble">{latestAlert.messages.community[language]}</div>
                  <p className="phone-time">{alertTime(latestAlert)}</p>
                </>
              ) : (
                <p className="phone-empty">NO ALERTS ISSUED</p>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* ── Crowdsourced Field Reports ── */}
      <section className="reports">
        <div className="section-heading">
          <div>
            <p className="eyebrow">FIELD REPORTS</p>
            <h2>Crowdsourced observations</h2>
          </div>
          <p className="sim-note">COMMUNITY &amp; FIELD OFFICIAL GROUND TRUTH</p>
        </div>
        <div className="reports-layout">
          <form className="report-form" onSubmit={submitReport}>
            <div className="sim-head">
              <p className="eyebrow">SUBMIT INCIDENT REPORT</p>
              <p className="sim-note">AUTO-VERIFIED FOR OFFICIALS</p>
            </div>
            <div className="report-fields">
              <label className="form-field">
                <span>REPORTER SOURCE</span>
                <select value={reportSource} onChange={(e) => setReportSource(e.target.value as "citizen" | "field_official")}>
                  <option value="citizen">CITIZEN (PENDING VERIFICATION)</option>
                  <option value="field_official">FIELD OFFICIAL (AUTO-VERIFIED)</option>
                </select>
              </label>
              <div className="form-row">
                <label className="form-field">
                  <span>LATITUDE</span>
                  <input type="number" step="0.01" value={reportLat} onChange={(e) => setReportLat(e.target.value)} required />
                </label>
                <label className="form-field">
                  <span>LONGITUDE</span>
                  <input type="number" step="0.01" value={reportLng} onChange={(e) => setReportLng(e.target.value)} required />
                </label>
              </div>
              <label className="form-field">
                <span>DESCRIPTION</span>
                <textarea rows={3} placeholder="Describe slope cracks, rockfalls, or water buildup..." value={reportDescription} onChange={(e) => setReportDescription(e.target.value)} required />
              </label>
              <label className="form-field">
                <span>PHOTO URL (OPTIONAL)</span>
                <input type="url" placeholder="https://..." value={reportPhotoUrl} onChange={(e) => setReportPhotoUrl(e.target.value)} />
              </label>
              <button type="submit" className="run" disabled={submittingReport}>
                {submittingReport ? "SUBMITTING..." : "SUBMIT REPORT →"}
              </button>
              {reportResult && (
                <p className={`sim-result ${reportResult.error ? "error" : "verified"}`}>
                  {reportResult.text}
                </p>
              )}
            </div>
          </form>
          <div className="report-list">
            {reports.length === 0 ? (
              <div className="alert-empty">NO RECENT INCIDENT REPORTS SUBMITTED</div>
            ) : (
              reports.map((report) => (
                <article className={`report-item ${report.status}`} key={report.id}>
                  <div className="report-meta">
                    <span className={`status-tag ${report.status}`}>{report.status.toUpperCase()}</span>
                    <span className="source-tag">{report.source === "field_official" ? "FIELD OFFICIAL" : "CITIZEN"}</span>
                    <span className="report-time">{reportTime(report)}</span>
                  </div>
                  <p className="report-desc">{report.description}</p>
                  <div className="report-submeta">
                    <span>{report.lat.toFixed(2)}°N / {report.lng.toFixed(2)}°E</span>
                    {report.photo_url && (
                      <a href={report.photo_url} target="_blank" rel="noreferrer" className="photo-link">VIEW ATTACHED PHOTO ↗</a>
                    )}
                  </div>
                </article>
              ))
            )}
          </div>
        </div>
      </section>
    </main>
  );
}
