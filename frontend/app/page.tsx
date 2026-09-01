"use client";

import { useEffect, useState } from "react";

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

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Dashboard() {
  const [zones, setZones] = useState<Zone[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/risk-scores`)
      .then((response) => {
        if (!response.ok) throw new Error("Risk service unavailable");
        return response.json();
      })
      .then(setZones)
      .catch(() => setError("Could not connect to the risk engine. Start the API on port 8000."));
  }, []);

  const severeCount = zones.filter((zone) => zone.risk_level === "Severe").length;
  const highCount = zones.filter((zone) => zone.risk_level === "High").length;

  return (
    <main>
      <header className="topbar"><div className="brand-mark">NER<span>•</span></div><div className="topbar-meta">EARLY WARNING NETWORK <b>● LIVE</b></div></header>
      <section className="hero"><div><p className="eyebrow">NORTHEAST REGION / FIELD VIEW</p><h1>Know the slope<br /><em>before it moves.</em></h1><p className="lede">A live picture of terrain pressure across monitored zones.</p></div><div className="timestamp">LAST UPDATED<br /><strong>{new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</strong></div></section>
      <section className="summary"><div><span>MONITORED ZONES</span><strong>{zones.length || "—"}</strong></div><div><span>HIGH RISK</span><strong className="amber">{highCount || "—"}</strong></div><div><span>SEVERE RISK</span><strong className="red">{severeCount || "—"}</strong></div><div className="summary-note">Rainfall data is simulated<br />for this demonstration.</div></section>
      <section className="content"><div className="section-heading"><div><p className="eyebrow">RISK OVERVIEW</p><h2>Current zone conditions</h2></div><div className="legend"><span className="dot low" />LOW <span className="dot medium" />MEDIUM <span className="dot high" />HIGH <span className="dot severe" />SEVERE</div></div>
        {error ? <div className="error">{error}</div> : <div className="zones">{zones.map((zone) => <article className="zone-card" key={zone.id}><div className={`risk-strip ${zone.risk_level.toLowerCase()}`} /><div className="zone-head"><div><h3>{zone.name}</h3><p>{zone.lat.toFixed(2)}°N / {zone.lng.toFixed(2)}°E</p></div><span className={`pill ${zone.risk_level.toLowerCase()}`}>{zone.risk_level}</span></div><div className="score"><strong>{zone.risk_score.toFixed(1)}</strong><span>/ 100 RISK SCORE</span></div><div className="rain"><span>24H RAINFALL PRESSURE <b>{Math.round(zone.rainfall_24h_norm * 100)}%</b></span><div className="meter"><i style={{ width: `${zone.rainfall_24h_norm * 100}%` }} /></div><span>7D BASELINE <b>{Math.round(zone.rainfall_7d_norm * 100)}%</b></span></div></article>)}</div>}
      </section>
    </main>
  );
}
