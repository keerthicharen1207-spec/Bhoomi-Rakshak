"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

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

type Zone = {
  id: number;
  name: string;
  state?: string;
  lat: number;
  lng: number;
  rainfall_24h_norm: number;
  rainfall_7d_norm: number;
  risk_score: number;
  risk_level: "Low" | "Medium" | "High" | "Severe";
  physics?: PhysicsData;
  ml?: MLData;
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

interface RiskMapProps {
  zones: Zone[];
  reports: Report[];
  selectedZoneId: number | null;
  onSelectZone: (zoneId: number) => void;
  onLocationSelect?: (lat: number, lng: number) => void;
}

const RISK_COLORS: Record<string, { stroke: string; fill: string }> = {
  Low: { stroke: "#578032", fill: "#a8d45f" },
  Medium: { stroke: "#8a7629", fill: "#d7c75b" },
  High: { stroke: "#a36c1e", fill: "#ecad4b" },
  Severe: { stroke: "#9b3626", fill: "#df6651" },
};

// Geographic Bounding Box strictly scoped to India
const INDIA_BOUNDS = L.latLngBounds([6.0, 68.0], [37.5, 97.5]);

export default function RiskMap({
  zones,
  reports,
  selectedZoneId,
  onSelectZone,
  onLocationSelect,
}: RiskMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const zonesLayerRef = useRef<L.LayerGroup | null>(null);
  const reportsLayerRef = useRef<L.LayerGroup | null>(null);

  // Keep latest callback references to avoid re-triggering map or layer effects
  const onLocationSelectRef = useRef(onLocationSelect);
  const onSelectZoneRef = useRef(onSelectZone);

  useEffect(() => {
    onLocationSelectRef.current = onLocationSelect;
  }, [onLocationSelect]);

  useEffect(() => {
    onSelectZoneRef.current = onSelectZone;
  }, [onSelectZone]);

  // Initialize Map ONCE on mount
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: [23.5, 84.0], // Center of India
      zoom: 5,
      minZoom: 4,
      maxZoom: 14,
      maxBounds: INDIA_BOUNDS,
      maxBoundsViscosity: 0.9,
      scrollWheelZoom: false, // Prevents scroll hijacking
      zoomControl: true,
    });

    // 100% Free OpenStreetMap tile server (no API keys required)
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
    }).addTo(map);

    map.on("click", (e: L.LeafletMouseEvent) => {
      const lat = parseFloat(e.latlng.lat.toFixed(2));
      const lng = parseFloat(e.latlng.lng.toFixed(2));
      if (lat >= 6.0 && lat <= 37.5 && lng >= 68.0 && lng <= 97.5) {
        onLocationSelectRef.current?.(lat, lng);
      }
    });

    const zonesLayer = L.layerGroup().addTo(map);
    const reportsLayer = L.layerGroup().addTo(map);

    zonesLayerRef.current = zonesLayer;
    reportsLayerRef.current = reportsLayer;
    mapInstanceRef.current = map;

    return () => {
      try {
        if (mapInstanceRef.current) {
          mapInstanceRef.current.stop();
          mapInstanceRef.current.remove();
          mapInstanceRef.current = null;
        }
      } catch {
        // Prevent unmount exceptions from in-flight Leaflet transitions
      }
    };
  }, []);

  // Update Zone Markers
  useEffect(() => {
    const zonesLayer = zonesLayerRef.current;
    if (!zonesLayer) return;

    zonesLayer.clearLayers();

    zones.forEach((zone) => {
      const colors = RISK_COLORS[zone.risk_level] || RISK_COLORS.Low;
      const isSelected = zone.id === selectedZoneId;

      const circle = L.circleMarker([zone.lat, zone.lng], {
        radius: isSelected ? 16 : 12,
        color: isSelected ? "#182322" : colors.stroke,
        weight: isSelected ? 3 : 2,
        fillColor: colors.fill,
        fillOpacity: 0.85,
      });

      const fsText = zone.physics ? zone.physics.factor_of_safety.toFixed(2) : "N/A";
      const qText = zone.physics ? `${zone.physics.flash_flood_q_m3s} m³/s` : "N/A";
      const lsProbText = zone.ml ? `${Math.round(zone.ml.landslide_susceptibility * 100)}%` : "N/A";
      const floodDepthText = zone.ml ? `${zone.ml.flood_depth_m.toFixed(1)}m` : "N/A";
      const triageText = zone.ml ? zone.ml.population_triage_level : "N/A";

      const popupContent = `
        <div style="font-family: sans-serif; min-width: 200px; padding: 2px;">
          <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px;">
            <strong style="font-size: 14px; color: #182322;">${zone.name}</strong>
            <span style="font-size: 9px; padding: 2px 6px; border-radius: 2px; font-weight: 600; background: ${colors.fill}44; color: ${colors.stroke};">
              ${zone.risk_level.toUpperCase()}
            </span>
          </div>
          <div style="font-size: 11px; color: #71807c; margin-bottom: 6px;">
            ${zone.state ? `<span style="font-weight: 600; color: #3b6b3a;">${zone.state}</span> · ` : ""}${zone.lat.toFixed(2)}°N, ${zone.lng.toFixed(2)}°E
          </div>
          <div style="font-size: 12px; margin-bottom: 6px; color: #182322;">
            Risk Score: <strong>${zone.risk_score.toFixed(1)} / 100</strong>
          </div>
          <div style="font-size: 10px; background: #f4f6f4; border-radius: 4px; padding: 6px; margin-bottom: 6px;">
            <div style="font-weight: 700; font-size: 9px; color: #465551; margin-bottom: 4px; border-bottom: 1px solid #e0e4df; padding-bottom: 2px;">
              PHYSICS &amp; GEOTECHNICAL
            </div>
            <div>Factor of Safety (FS): <strong>${fsText}</strong></div>
            <div>Peak Discharge (Q): <strong>${qText}</strong></div>
          </div>
          <div style="font-size: 10px; background: #f4f6f4; border-radius: 4px; padding: 6px;">
            <div style="font-weight: 700; font-size: 9px; color: #465551; margin-bottom: 4px; border-bottom: 1px solid #e0e4df; padding-bottom: 2px;">
              ML INFERENCE PREDICTIONS
            </div>
            <div>Landslide Prob: <strong>${lsProbText}</strong></div>
            <div>Flood Depth: <strong>${floodDepthText}</strong></div>
            <div>Evac Triage: <strong>${triageText}</strong></div>
          </div>
        </div>
      `;

      circle.bindPopup(popupContent);
      circle.on("click", () => {
        onSelectZoneRef.current(zone.id);
      });

      circle.bindTooltip(
        `<span style="font-size: 10px; font-weight: 600;">${zone.name.toUpperCase()}${zone.state ? ` (${zone.state})` : ""} · ${zone.risk_level.toUpperCase()}</span>`,
        { permanent: false, direction: "top", offset: [0, -10] }
      );

      circle.addTo(zonesLayer);
    });
  }, [zones, selectedZoneId]);

  // Update Report Markers
  useEffect(() => {
    const reportsLayer = reportsLayerRef.current;
    if (!reportsLayer) return;

    reportsLayer.clearLayers();

    reports.forEach((report) => {
      const isOfficial = report.source === "field_official";
      const isVerified = report.status === "verified";
      const markerColor = isVerified ? "#578032" : "#a36c1e";

      const iconHtml = `
        <div style="
          background: ${markerColor};
          color: #fff;
          width: 20px;
          height: 20px;
          border-radius: 50%;
          border: 2px solid #fff;
          box-shadow: 0 2px 5px rgba(0,0,0,0.3);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 10px;
          font-weight: 700;
        ">
          ${isOfficial ? "O" : "C"}
        </div>
      `;

      const customIcon = L.divIcon({
        html: iconHtml,
        className: "custom-report-marker",
        iconSize: [20, 20],
        iconAnchor: [10, 10],
      });

      const marker = L.marker([report.lat, report.lng], { icon: customIcon });

      const reportTimeStr = new Date(report.created_at).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });

      const popupContent = `
        <div style="font-family: sans-serif; min-width: 170px; max-width: 240px; padding: 2px;">
          <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px;">
            <span style="font-size: 9px; font-weight: 600; color: ${markerColor};">
              ${isOfficial ? "FIELD OFFICIAL" : "CITIZEN"}
            </span>
            <span style="font-size: 9px; padding: 1px 4px; border-radius: 2px; background: ${isVerified ? "#e8f4d6" : "#fff0d9"}; color: ${markerColor};">
              ${report.status.toUpperCase()}
            </span>
          </div>
          <p style="margin: 6px 0; font-size: 12px; line-height: 1.5; color: #182322;">
            ${report.description}
          </p>
          <div style="font-size: 9px; color: #71807c; margin-top: 6px; display: flex; justify-content: space-between;">
            <span>${report.lat.toFixed(2)}°N, ${report.lng.toFixed(2)}°E</span>
            <span>${reportTimeStr}</span>
          </div>
          ${
            report.photo_url
              ? `<div style="margin-top: 6px;"><a href="${report.photo_url}" target="_blank" rel="noreferrer" style="font-size: 9px; color: #668b44;">View Photo ↗</a></div>`
              : ""
          }
        </div>
      `;

      marker.bindPopup(popupContent);
      marker.addTo(reportsLayer);
    });
  }, [reports]);

  return (
    <div className="map-wrapper">
      <div ref={mapContainerRef} className="map-container" />
      <div className="map-hint">
        <span>USE +/- BUTTONS TO ZOOM · CLICK ANYWHERE IN INDIA TO PICK COORDINATES · CLICK ZONES TO INSPECT</span>
      </div>
    </div>
  );
}
