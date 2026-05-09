# NEXUS IQ — Industrial Intelligence Platform

> AI-prioritized alarms and role-aware HMI for small-scale industrial control rooms.

## Problem Solved

Traditional HMIs flood operators with undifferentiated alarms, burying critical events in noise. NEXUS IQ uses statistical anomaly detection to surface only what matters, routed to the right role at the right time. The result is faster response, fewer missed events, and a control room that actually works at scale.

## Features

- **3 Role UIs** — Operator · Engineer · Manager, each with dedicated navigation, dashboards, and permissions
- **Live Z-score + Slope Anomaly Detection** — Statistical engine identifies deviations in real time
- **Full Alarm Lifecycle** — Raise · Acknowledge · Suppress · Persist to SQLite
- **Real Sensor Pipeline** — FastAPI backend + SQLite (WAL mode) + standalone PLC simulator
- **Report Generation** — CSV + HTML download with shift-level granularity
- **Demo Mode** — One-click CRITICAL alarm demonstration for live presentations
- **Configurable Thresholds** — Temperature, pressure, RPM limits persisted in localStorage
- **Light / Dark Theme** — Full theme toggle with CSS variable architecture

## Quick Start

```bash
chmod +x start.sh && ./start.sh
```

Open [http://localhost:5000](http://localhost:5000) — login with `admin@hmi.com` / `password123`.

## 60-Second Demo Script

| Step | Action |
|------|--------|
| 1 | Login as **Operator** → click **⬡ DEMO MODE** |
| 2 | Navigate to `/alarms` → **ACK ALL** → watch counts update live |
| 3 | Navigate to `/ai-insights` → Z-scores updating every 2s |
| 4 | Logout → Login as **Manager** → `/manager/kpis` |
| 5 | Logout → Login as **Engineer** → `/engineer/signals` → search `"PT"` |

## Architecture

```
┌─────────────┐    HTTP/JSON     ┌──────────────┐    SQLite   ┌──────────┐
│  Dash App   │ ◄──────────────► │  FastAPI API │ ◄──────────►│ nexus.db │
│ (port 5000) │                  │  (port 8000) │             └──────────┘
└─────────────┘                  └──────┬───────┘
                                        ▲
                                        │ POST /api/sensor/ingest
                                 ┌──────┴───────┐
                                 │  sensor_sim  │
                                 │  (PLC sim)   │
                                 └──────────────┘
```

| Layer | Technology |
|-------|-----------|
| Frontend | Python Dash + Plotly + Bootstrap (dark HMI theme) |
| Backend | FastAPI + SQLite with WAL mode |
| AI Engine | Z-score anomaly detection + linear regression slope |
| Sensor Sim | Sine wave temp · random walk pressure · stepped RPM |

## Stack

Python 3.10+ · Dash 2.14 · FastAPI 0.104 · SQLite 3
