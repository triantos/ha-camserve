# Camserve for Home Assistant

Custom integration for [Camserve](https://github.com/triantos/camserve) — a self-hosted security camera recording and motion detection system.

## Features

- **Camera entities** — each Camserve camera appears as an HA camera with live RTSP streaming and snapshots
- **Media browser** — browse and play event clips organized by camera, with thumbnails and classification badges
- **Authenticated proxy** — event clips and thumbnails are proxied through HA so the Companion App can display them without direct access to Camserve
- **Rich notifications** — pair with the included automation to get mobile notifications with embedded thumbnails and "View Clip" / "Live View" action buttons

## Installation (HACS)

1. In Home Assistant, go to **HACS → Integrations → ⋮ (top right) → Custom repositories**
2. Add `https://github.com/triantos/ha-camserve` with category **Integration**
3. Search for "Camserve" and click **Download**
4. Restart Home Assistant
5. Go to **Settings → Integrations → Add Integration → Camserve**
6. Enter your Camserve server URL (e.g. `http://camserve.local:8080`)

## Notification Automation

See [`automation_camserve_detection.yaml`](automation_camserve_detection.yaml) for a ready-to-use automation that sends mobile notifications when Camserve detects a person, vehicle, or package. The notification includes:

- Thumbnail image from the event
- "View Clip" button → opens the event in HA media browser
- "Live View" button → opens the camera's live stream

## Requirements

- A running Camserve instance with the `/api/cameras/{id}/snapshot` endpoint (v0.2+)
- HA's [Stream](https://www.home-assistant.io/integrations/stream/) integration (for live RTSP streams)
