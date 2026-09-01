# Ticket 4: Incident Reports (Crowdsourced & Field Official)

## Objective
Implement crowdsourced and field official incident reporting system with auto-verification for officials and pending status for citizens.

## Changes
- Backend: ackend/reports.py status determination based on source.
- Backend: SQLite eports table creation in ackend/main.py.
- Backend: POST /reports and GET /reports API endpoints in ackend/main.py.
- Backend: Tests in ackend/tests/test_reports.py and ackend/tests/test_api.py.
- Frontend: Field reports submission form and feed in rontend/app/page.tsx & rontend/app/styles.css.
- Docs: Updated README.md API table.

## Status
Completed & Verified
