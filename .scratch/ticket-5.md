# Ticket 5: Geospatial Interactive Map Visualization

## Objective
Implement an interactive Leaflet-powered geospatial map visualization for the Northeast India monitoring zones and crowdsourced/official incident reports.

## Changes
- Frontend Component: rontend/app/RiskMap.tsx with dynamic client-side Leaflet rendering, custom colored circle markers for risk zones (Low, Medium, High, Severe), tooltips, and informational popups.
- Interactive Incident Markers: Custom map markers differentiating verified field official observations vs pending citizen reports with popup metadata.
- Interactive Map Coordinates Selection: Clicking anywhere on the map sets the coordinates for incident report submission.
- Dashboard Integration: Embedded RiskMap dynamically in rontend/app/page.tsx with legend and styling in rontend/app/styles.css.

## Status
Completed & Verified