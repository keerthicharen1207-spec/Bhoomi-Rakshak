"use client";

import { useCallback, useEffect, useState } from "react";

type Zone = {
  id: number;
  name: string;
  lat: number;
  lng: number;
  rainfall_24h_norm: number;
  rainfall_7d_norm: number;
  risk_score: number;
  risk_level: "Low" | "Medium" | "High" | "Severe";
};

type AlertMessages = {
  authority: string;
  community: { en: string; as: string; nl: string };
};

type Alert = {
  id: number;
  zone_id: number;
  zone_name: string;
  level: "High" | "Severe";
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

  const loadZones = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/risk-scores`);
      if (!response.ok) throw new Error("Risk service unavailable");
      const data: Zone[] = await response.json();
      setZones(data);
      setError(null);
      setSelectedZoneId((current) => current ?? data[0]?.id ?? null);
      setUpdatedAt(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    } catch {
      setError("Could not connect to the risk engine. Start the API on port 8000.");
    }
  }, []);

  const loadAlerts = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/alerts`);
      if (!response.ok) throw new Error("Alert feed unavailable");
      setAlerts(await response.json());
    } catch {
      setAlerts([]);
    }
  }, []);

  const loadReports = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/reports`);
      if (!response.ok) throw new Error("Reports feed unavailable");
      setReports(await response.json());
    } catch {
      setReports([]);
    }
  }, []);

  useEffect(() => {
    loadZones();
    loadAlerts();
    loadReports();
  }, [loadZones, loadAlerts, loadReports]);

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
          lat: parseFloat(reportLat) || 0,
          lng: parseFloat(reportLng) || 0,
          description: reportDescription.trim(),
          photo_url: reportPhotoUrl.trim(),
          source: reportSource,
        }),
      });
      if (!response.ok) throw new Error("Submission failed");
      setReportDescription("");
      setReportPhotoUrl("");
      setReportResult({ text: "INCIDENT REPORT RECORDED SUCCESSFULLY" });
      await loadReports();
    } catch {
      setReportResult({ text: "FAILED TO SUBMIT REPORT — CHECK BACKEND SERVICE", error: true });
    } finally {
      setSubmittingReport(false);
    }
  }

  async function runSimulation() {
    if (selectedZoneId === null) return;
    setSimulating(true);
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
        text: `${updated.name.toUpperCase()} → ${updated.risk_level.toUpperCase()} · SCORE ${updated.risk_score.toFixed(1)}`,
        level: updated.risk_level.toLowerCase(),
      });
    } catch {
      setResult({ text: "SIMULATION FAILED — IS THE RISK ENGINE RUNNING?", level: "error" });
    } finally {
      setSimulating(false);
    }
  }

  const severeCount = zones.filter((zone) => zone.risk_level === "Severe").length;
  const highCount = zones.filter((zone) => zone.risk_level === "High").length;
  const sliderPercent = (rainfallMm / RAINFALL_MAX_MM) * 100;
  const latestAlert = alerts[0] ?? null;

  return (
    <main>
      <header className="topbar"><div className="brand-mark">NER<span>•</span></div><div className="topbar-meta">EARLY WARNING NETWORK <b>● LIVE</b></div></header>
      <section className="hero"><div><p className="eyebrow">NORTHEAST REGION / FIELD VIEW</p><h1>Know the slope<br /><em>before it moves.</em></h1><p className="lede">A live picture of terrain pressure across monitored zones.</p></div><div className="timestamp">LAST UPDATED<br /><strong>{updatedAt}</strong></div></section>
      <section className="summary"><div><span>MONITORED ZONES</span><strong>{zones.length || "—"}</strong></div><div><span>HIGH RISK</span><strong className="amber">{highCount || "—"}</strong></div><div><span>SEVERE RISK</span><strong className="red">{severeCount || "—"}</strong></div><div className="summary-note">Rainfall data is simulated<br />for this demonstration.</div></section>
      <section className="content"><div className="section-heading"><div><p className="eyebrow">RISK OVERVIEW</p><h2>Current zone conditions</h2></div><div className="legend"><span className="dot low" />LOW <span className="dot medium" />MEDIUM <span className="dot high" />HIGH <span className="dot severe" />SEVERE</div></div>
        <div className="simulator">
          <div className="sim-head"><p className="eyebrow">RAINFALL SIMULATOR</p><p className="sim-note">SIMULATED FEED — DRIVES THE RISK ENGINE DIRECTLY</p></div>
          <div className="sim-controls">
            <label className="sim-field"><span>TARGET ZONE</span><select value={selectedZoneId ?? zones[0]?.id ?? ""} onChange={(event) => setSelectedZoneId(Number(event.target.value))} disabled={zones.length === 0}>{zones.map((zone) => <option key={zone.id} value={zone.id}>{zone.name.toUpperCase()}</option>)}</select></label>
            <label className="sim-field"><span>24H RAINFALL<b>{rainfallMm}MM · {rainfallBand(rainfallMm)}</b></span><input type="range" min={0} max={RAINFALL_MAX_MM} step={5} value={rainfallMm} onChange={(event) => setRainfallMm(Number(event.target.value))} style={{ background: `linear-gradient(to right, #182322 ${sliderPercent}%, #edf1eb ${sliderPercent}%)` }} /></label>
            <button type="button" className="run" onClick={runSimulation} disabled={simulating || selectedZoneId === null}>{simulating ? "SIMULATING…" : "RUN SIMULATION →"}</button>
            <div className="sim-presets">{PRESETS.map((preset) => <button key={preset.mm} type="button" className={rainfallMm === preset.mm ? "chip active" : "chip"} onClick={() => setRainfallMm(preset.mm)}>{preset.label}</button>)}</div>
          </div>
          {result && <p className={`sim-result ${result.level}`}>{result.text}</p>}
        </div>
        {error ? <div className="error">{error}</div> : <div className="zones">{zones.map((zone) => <article className={`zone-card ${zone.risk_level.toLowerCase()}`} key={zone.id}><div className={`risk-strip ${zone.risk_level.toLowerCase()}`} /><div className="zone-head"><div><h3>{zone.name}</h3><p>{zone.lat.toFixed(2)}°N / {zone.lng.toFixed(2)}°E</p></div><span className={`pill ${zone.risk_level.toLowerCase()}`}>{zone.risk_level}</span></div><div className="score"><strong>{zone.risk_score.toFixed(1)}</strong><span>/ 100 RISK SCORE</span></div><div className="rain"><span>24H RAINFALL PRESSURE <b>{Math.round(zone.rainfall_24h_norm * 100)}%</b></span><div className="meter"><i style={{ width: `${zone.rainfall_24h_norm * 100}%` }} /></div><span>7D BASELINE <b>{Math.round(zone.rainfall_7d_norm * 100)}%</b></span></div></article>)}</div>}
      </section>
      <section className="alerts">
        <div className="section-heading"><div><p className="eyebrow">ALERT FEED</p><h2>Threshold crossings</h2></div><p className="sim-note">AUTO-GENERATED ON ESCALATION INTO HIGH / SEVERE</p></div>
        <div className="alerts-layout">
          <div className="alert-list">
            {alerts.length === 0 ? <div className="alert-empty">NO ALERTS ISSUED — ALL ZONES BELOW THE WARNING THRESHOLD</div> : alerts.map((alert) => <article className={`alert-item ${alert.level.toLowerCase()}`} key={alert.id}><div className="alert-meta"><span className={`level-tag ${alert.level.toLowerCase()}`}>{alert.level.toUpperCase()}</span><span>{alert.zone_name.toUpperCase()}</span><span>{alertTime(alert)}</span></div><p>{alert.messages.authority}</p></article>)}
          </div>
          <div className="sms-mock">
            <div className="sim-head"><p className="eyebrow">COMMUNITY SMS</p><p className="sim-note">MOCKED VIEW — NO REAL DELIVERY</p></div>
            <div className="lang-toggle">{LANGUAGES.map((lang) => <button key={lang.code} type="button" className={language === lang.code ? "chip active" : "chip"} onClick={() => setLanguage(lang.code)}>{lang.label}</button>)}</div>
            <div className="phone">
              {latestAlert ? (<><p className="phone-to">TO: SUBSCRIBERS — {latestAlert.zone_name.toUpperCase()}</p><div className="phone-bubble">{latestAlert.messages.community[language]}</div><p className="phone-time">{alertTime(latestAlert)}</p></>) : <p className="phone-empty">NO ALERTS ISSUED</p>}
            </div>
          </div>
        </div>
      </section>
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
                <select
                  value={reportSource}
                  onChange={(e) => setReportSource(e.target.value as "citizen" | "field_official")}
                >
                  <option value="citizen">CITIZEN (PENDING VERIFICATION)</option>
                  <option value="field_official">FIELD OFFICIAL (AUTO-VERIFIED)</option>
                </select>
              </label>
              <div className="coords-row">
                <label className="form-field">
                  <span>LATITUDE (°N)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={reportLat}
                    onChange={(e) => setReportLat(e.target.value)}
                    required
                  />
                </label>
                <label className="form-field">
                  <span>LONGITUDE (°E)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={reportLng}
                    onChange={(e) => setReportLng(e.target.value)}
                    required
                  />
                </label>
              </div>
              <label className="form-field">
                <span>INCIDENT OBSERVATION</span>
                <textarea
                  rows={3}
                  value={reportDescription}
                  onChange={(e) => setReportDescription(e.target.value)}
                  placeholder="Describe ground cracks, debris, road blockage..."
                  required
                />
              </label>
              <label className="form-field">
                <span>PHOTO URL (OPTIONAL)</span>
                <input
                  type="url"
                  value={reportPhotoUrl}
                  onChange={(e) => setReportPhotoUrl(e.target.value)}
                  placeholder="https://example.com/photo.jpg"
                />
              </label>
              <button type="submit" className="run" disabled={submittingReport || !reportDescription.trim()}>
                {submittingReport ? "SUBMITTING…" : "SUBMIT REPORT →"}
              </button>
              {reportResult && (
                <p className={`report-status ${reportResult.error ? "error" : "success"}`}>
                  {reportResult.text}
                </p>
              )}
            </div>
          </form>
          <div className="report-list">
            {reports.length === 0 ? (
              <div className="alert-empty">NO FIELD REPORTS FILED YET</div>
            ) : (
              reports.map((report) => (
                <article className={`report-card ${report.status}`} key={report.id}>
                  <div className="report-meta">
                    <span className={`status-tag ${report.status}`}>{report.status.toUpperCase()}</span>
                    <span>{report.source === "field_official" ? "FIELD OFFICIAL" : "CITIZEN"}</span>
                    <span>{report.lat.toFixed(2)}°N / {report.lng.toFixed(2)}°E</span>
                    <span>{reportTime(report)}</span>
                  </div>
                  <p className="report-desc">{report.description}</p>
                  {report.photo_url && (
                    <a
                      href={report.photo_url}
                      target="_blank"
                      rel="noreferrer"
                      className="photo-link"
                    >
                      VIEW ATTACHED PHOTO ↗
                    </a>
                  )}
                </article>
              ))
            )}
          </div>
        </div>
      </section>
    </main>
  );
}
