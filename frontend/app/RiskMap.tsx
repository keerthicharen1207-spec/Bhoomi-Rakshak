"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

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

  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: [25.5, 93.0],
      zoom: 7,
      minZoom: 6,
      maxZoom: 14,
      scrollWheelZoom: true,
    });

    L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
      attribution: '&copy; OpenStreetMap &copy; CARTO',
      maxZoom: 19,
    }).addTo(map);

    map.on("click", (e: L.LeafletMouseEvent) => {
      if (onLocationSelect) {
        onLocationSelect(parseFloat(e.latlng.lat.toFixed(2)), parseFloat(e.latlng.lng.toFixed(2)));
      }
    });

    const zonesLayer = L.layerGroup().addTo(map);
    const reportsLayer = L.layerGroup().addTo(map);

    zonesLayerRef.current = zonesLayer;
    reportsLayerRef.current = reportsLayer;
    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, [onLocationSelect]);

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

      const popupContent = `
        <div style="font-family: sans-serif; min-width: 160px; padding: 2px;">
          <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px;">
            <strong style="font-size: 15px; color: #182322;">${zone.name}</strong>
            <span style="font-size: 9px; padding: 2px 6px; border-radius: 2px; font-weight: 600; background: ${colors.fill}44; color: ${colors.stroke};">
              ${zone.risk_level.toUpperCase()}
            </span>
          </div>
          <div style="font-size: 11px; color: #71807c; margin-bottom: 6px;">
            ${zone.lat.toFixed(2)} deg N, ${zone.lng.toFixed(2)} deg E
          </div>
          <div style="font-size: 12px; margin-bottom: 4px; color: #182322;">
            Risk Score: <strong>${zone.risk_score.toFixed(1)} / 100</strong>
          </div>
          <div style="font-size: 11px; color: #71807c;">
            24h Rain: <strong>${Math.round(zone.rainfall_24h_norm * 100)}%</strong> | 7d: <strong>${Math.round(zone.rainfall_7d_norm * 100)}%</strong>
          </div>
        </div>
      `;

      circle.bindPopup(popupContent);
      circle.on("click", () => {
        onSelectZone(zone.id);
      });

      circle.bindTooltip(
        `<span style="font-size: 10px; font-weight: 600;">${zone.name.toUpperCase()} (${zone.risk_level.toUpperCase()})</span>`,
        { permanent: false, direction: "top", offset: [0, -10] }
      );

      circle.addTo(zonesLayer);
    });
  }, [zones, selectedZoneId, onSelectZone]);

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
            <span>${report.lat.toFixed(2)} deg N, ${report.lng.toFixed(2)} deg E</span>
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
        <span>CLICK ANYWHERE ON MAP TO PICK COORDINATES · CLICK ZONES TO INSPECT</span>
      </div>
    </div>
  );
}

