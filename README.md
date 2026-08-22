# RoadGuardian AI — Command Center & Emergency Response Orchestration

RoadGuardian AI is an autonomous AI visual surveillance, incident detection, automated prioritization, and emergency response orchestration system.

---

## Architecture Overview

```
roadguardian-ai/
├── frontend/                  # React 18 + TypeScript + Vite + Tailwind CSS
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.tsx             # Command HUD, IST clock, Stepper & Simulation trigger
│   │   │   ├── CameraGrid.tsx         # 6 Live CCTV Feeds with Thermal Vision & Bounding Boxes
│   │   │   ├── PriorityList.tsx       # Dynamic Ranked Priority Queue with Rank-shift animations
│   │   │   ├── DetailInspector.tsx    # Feature Matrix, Keyframes/Video Replay, AI Report & Explainability
│   │   │   ├── ResponseOrchestrator.tsx # Hospital, Fire & Police Dispatch Units with ETAs
│   │   │   ├── DigitalTwinMap.tsx     # GIS Vector Map with Camera Nodes & Dispatch Route Paths
│   │   │   └── CopilotChat.tsx        # LLM Decision Assistant (Judge Step 10 context reasoning)
│   │   ├── context/IncidentContext.tsx# Shared state store & 5-step simulation pipeline
│   │   ├── services/apiService.ts     # In-memory database engine + FastAPI HTTP client
│   │   └── types/incident.ts          # Unified data contracts
│   └── package.json
└── backend/                   # FastAPI + SQLite + Orchestration Engine
    ├── main.py                # REST API endpoints (GET /incidents, POST /incidents, POST /reset)
    ├── store.py               # SQLite storage with JSON column serialization
    ├── orchestrator.py        # Severity calculation, re-ranking algorithm & report generation
    ├── models.py              # Pydantic schema validation
    ├── test_api.py            # Automated end-to-end integration test
    └── requirements.txt
```

---

## 10-Step Judge Demonstration Journey

1. **Step 1: Baseline Surveillance Grid** — View 6 live camera feeds. `CAM01_001` is initially at **Rank #3** (Severity 45).
2. **Step 2: Trigger Simulation** — Click **"⚡ RUN LIVE INCIDENT SIMULATION"** in the top header.
3. **Step 3: Feature Extraction** — Visual evidence updates structured observations: `vehicle_count: 3`, `person_on_road: true`, `fire_smoke: true`, `rollover: true`, `traffic_impact: 'critical'`.
4. **Step 4: Severity Escalation** — Dynamic AI severity engine recalculates score from **45 ➔ 96/100 (CRITICAL)**.
5. **Step 5: Dynamic Re-ranking** — Animated rank shift moves `CAM01_001` from **Priority #3 ➔ PRIORITY #1**.
6. **Step 6: Evidence & Timeline Replay** — Switch between Keyframe evidence and CCTV video clip replay with timestamped timeline.
7. **Step 7: "Why Priority Changed" Explainability** — Inspect deterministic scoring contributions (+25 Pedestrian, +20 Fire/Plume, +15 Rollover).
8. **Step 8: Automated Dispatch** — Response Orchestrator activates **Hospital Trauma Unit #04**, **Fire Engine #12**, and **Highway Police #09** with ETAs.
9. **Step 9: Road Digital Twin GIS Map** — Switch to the "Road Digital Twin" tab to inspect GIS road network, epicenter ping ring, and dispatched vehicle vector routes.
10. **Step 10: Interactive AI Copilot** — Switch to "AI Copilot" tab and click *"WHY IS THIS INCIDENT PRIORITY #1?"* to verify LLM reasoning synchronized with live state.

---

## Running the Application

### 1. Launch Frontend Web App
```bash
cd frontend
npm run dev
```
Open **http://localhost:3000** in your browser.

*(Note: The frontend includes a standalone in-memory state engine and works out of the box with zero setup. You can also toggle the backend API on/off with the header button).*

### 2. (Optional) Launch FastAPI Backend
```bash
cd backend
pip install -r requirements.txt
python main.py
```
Backend API will be live at **http://localhost:8000** with interactive docs at **http://localhost:8000/docs**.

### 3. Run Backend Integration Tests
```bash
cd backend
python test_api.py
```
