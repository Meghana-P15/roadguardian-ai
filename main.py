import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import List, Dict, Any, Optional

import store
import orchestrator
from models import (
    IncidentInput,
    IncidentSummaryOutput,
    IncidentDetailOutput,
    DispatchRecord,
    DeliveryLog,
    SafeWatchEvent
)

app = FastAPI(
    title="RoadGuardian AI — Autonomous Incident & Public Safety Command API",
    description="Backend Engine for Multimodal Road Intelligence, Priority Escalation & Emergency Response Orchestration",
    version="2.0.0"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount evidence static files
evidence_dir = os.path.join(os.path.dirname(__file__), "evidence")
os.makedirs(evidence_dir, exist_ok=True)
app.mount("/evidence", StaticFiles(directory=evidence_dir), name="evidence")

@app.on_event("startup")
def on_startup():
    store.init_db()
    existing = store.get_all_incidents()
    if not existing:
        store.seed_baseline_data()
        orchestrator.reprioritize_all_incidents()

import cybershield

@app.get("/")
@app.get("/health")
def root():
    return {
        "status": "online",
        "service": "RoadGuardian AI Command Platform",
        "version": "2.0.0",
        "mode": "DEMO_SIMULATION_SANDBOX",
        "endpoints": [
            "/incidents",
            "/incidents/{id}",
            "/dispatches",
            "/delivery-logs",
            "/safewatch",
            "/safewatch/{id}/review",
            "/cybershield/events",
            "/cybershield/metrics",
            "/cybershield/correlate",
            "/simulation/scenario/{scenario_name}",
            "/reset"
        ]
    }

# ==========================================
# CyberShield Defensive Security Endpoints
# ==========================================

@app.get("/cybershield/events")
def list_cybershield_events():
    return cybershield.get_cybershield_events()

@app.get("/cybershield/metrics")
def get_cybershield_metrics():
    return cybershield.get_cybershield_metrics()

@app.post("/cybershield/correlate")
def correlate_cybershield_events(incident_id: Optional[str] = Body(None, embed=True)):
    return cybershield.correlate_cyber_physical_events(incident_id)

# ==========================================
# Incidents Endpoints
# ==========================================

@app.get("/incidents", response_model=List[IncidentSummaryOutput])
def list_incidents():
    incidents = store.get_all_incidents()
    return sorted(incidents, key=lambda x: x.get("priority_rank", 99))

@app.get("/incidents/{incident_id}", response_model=IncidentDetailOutput)
def get_incident_detail(incident_id: str):
    inc = store.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return inc

@app.post("/incidents", response_model=IncidentDetailOutput)
def ingest_or_update_incident(payload: IncidentInput):
    inc_dict = payload.model_dump(exclude_unset=True)
    
    # Calculate severity score, label & factors if not explicitly provided
    if "features" in inc_dict and ("severity_score" not in inc_dict or inc_dict["severity_score"] is None):
        score, label, factors = orchestrator.calculate_severity(inc_dict["features"], inc_dict.get("type", "collision"))
        inc_dict["severity_score"] = score
        inc_dict["severity_label"] = label
        inc_dict["severity_factors"] = factors
        
    # Auto-pick response workflow if not provided
    if "response_workflow" not in inc_dict or not inc_dict["response_workflow"]:
        inc_dict["response_workflow"] = orchestrator.pick_response_workflow(
            inc_dict.get("features", {}),
            inc_dict.get("severity_label", "Medium"),
            inc_dict.get("type", "collision")
        )
        
    # Auto-generate report if not provided
    if "report" not in inc_dict or not inc_dict["report"]:
        inc_dict["report"] = orchestrator.generate_report(inc_dict)
        
    # Upsert in database
    store.upsert_incident(inc_dict)
    
    # Trigger full priority re-ranking
    orchestrator.reprioritize_all_incidents()
    
    # Orchestrate dispatches if critical/high
    if inc_dict.get("severity_score", 0) >= 65:
        orchestrator.orchestrate_dispatches_for_incident(payload.incident_id)
    
    updated = store.get_incident(payload.incident_id)
    return updated

# ==========================================
# Dispatch Center Endpoints
# ==========================================

@app.get("/dispatches", response_model=List[DispatchRecord])
def list_dispatches():
    return store.get_all_dispatches()

@app.post("/dispatches/{dispatch_id}/acknowledge")
def acknowledge_dispatch(dispatch_id: str):
    disp = store.update_dispatch_status(dispatch_id, "ACKNOWLEDGED")
    if not disp:
        raise HTTPException(status_code=404, detail="Dispatch not found")
    return disp

@app.post("/dispatches/{dispatch_id}/progress")
def progress_dispatch(dispatch_id: str, payload: Dict[str, Any] = Body(default={}), new_status: Optional[str] = None):
    status_val = new_status or payload.get("new_status") or payload.get("status") or "EN_ROUTE"
    disp = store.update_dispatch_status(dispatch_id, status_val)
    if not disp:
        raise HTTPException(status_code=404, detail="Dispatch not found")
    
    # Audit trail delivery log
    now_time = datetime.now().strftime("%H:%M:%S")
    store.add_delivery_log({
        "log_id": f"LOG-PROGRESS-{dispatch_id}-{int(datetime.now().timestamp()) % 10000}",
        "dispatch_id": dispatch_id,
        "recipient_type": f"{disp.get('unit_type', 'EMERGENCY')}_DISPATCH",
        "unit_type": disp.get("unit_type", "UNIT"),
        "message_summary": f"SIMULATED PROGRESS UPDATE: Unit {disp.get('unit_id')} status advanced to [{status_val}].",
        "delivery_status": "SIMULATED ALERT DELIVERED",
        "timestamp": now_time
    })
    
    return disp

@app.get("/delivery-logs", response_model=List[DeliveryLog])
def list_delivery_logs():
    return store.get_all_delivery_logs()

# ==========================================
# SafeWatch Public Safety Endpoints
# ==========================================

@app.get("/safewatch", response_model=List[SafeWatchEvent])
def list_safewatch_events():
    return store.get_all_safewatch_events()

@app.get("/safewatch/{event_id}", response_model=SafeWatchEvent)
def get_safewatch_event(event_id: str):
    evt = store.get_safewatch_event(event_id)
    if not evt:
        raise HTTPException(status_code=404, detail=f"SafeWatch event {event_id} not found")
    return evt

@app.post("/safewatch/{event_id}/review")
def review_safewatch_event(
    event_id: str,
    approved: bool = Body(..., embed=True),
    operator_id: str = Body("COMMANDER-01", embed=True)
):
    evt = store.get_safewatch_event(event_id)
    if not evt:
        raise HTTPException(status_code=404, detail=f"SafeWatch event {event_id} not found")
    
    now_time = datetime.now().strftime("%H:%M:%S")
    evt["approved_by"] = operator_id
    evt["approval_timestamp"] = now_time
    
    timeline = evt.get("timeline", [])
    
    if approved:
        evt["status"] = "APPROVED"
        evt["simulated_alert_sent"] = True
        timeline.append({
            "time": now_time,
            "event": f"HUMAN_REVIEW_APPROVED: Operator {operator_id} confirmed safety anomaly. SIMULATED AUTHORIZED ALERT dispatched to Women's Safety Response Team / Patrol.",
            "event_type": "HUMAN_REVIEW_APPROVED"
        })
        # Add to alert delivery logs
        store.add_delivery_log({
            "log_id": f"LOG-SAFE-{event_id}",
            "dispatch_id": event_id,
            "recipient_type": "SHE_TEAM",
            "unit_type": "SAFETY_PATROL",
            "message_summary": f"SIMULATED AUTHORIZED ALERT: Safety assistance advisory confirmed at {evt.get('location', {}).get('name')}.",
            "delivery_status": "SIMULATED ALERT DELIVERED",
            "timestamp": now_time
        })
    else:
        evt["status"] = "REJECTED"
        timeline.append({
            "time": now_time,
            "event": f"HUMAN_REVIEW_DISMISSED: Operator {operator_id} reviewed and closed anomaly as routine activity.",
            "event_type": "HUMAN_REVIEW_DISMISSED"
        })
        
    evt["timeline"] = timeline
    updated = store.upsert_safewatch_event(evt)
    return updated

# ==========================================
# Multi-Scenario Live Simulation Endpoints
# ==========================================

@app.post("/simulation/scenario/{scenario_name}")
def trigger_scenario(scenario_name: str):
    now_time = datetime.now().strftime("%H:%M:%S")
    
    if scenario_name == "collision_escalation":
        # Scenario A: Collision Escalation on CAM01_001
        features = {
            "vehicle_count": 3,
            "person_on_road": True,
            "fire_smoke": True,
            "rollover": True,
            "traffic_impact": "critical",
            "lane_blockage": 3,
            "confidence": 0.97
        }
        score, label, factors = orchestrator.calculate_severity(features, "collision")
        
        timeline_events = [
            {"time": now_time, "event": "DETECTION_RECEIVED: Multi-spectral sensors on CAM-01 captured severe multi-vehicle collision.", "event_type": "DETECTION_RECEIVED"},
            {"time": now_time, "event": "OBSERVATION_UPDATED: Structured observation verified: 3 vehicles, pedestrian on road, active fire plume, and rollover.", "event_type": "OBSERVATION_UPDATED"},
            {"time": now_time, "event": f"SEVERITY_RECALCULATED: Dynamic score escalated from 45 -> {score}/100 ({label.upper()}).", "event_type": "SEVERITY_RECALCULATED"},
            {"time": now_time, "event": "PRIORITY_CHANGED: CAM01_001 re-ranked from Priority #3 -> PRIORITY #1 in active queue.", "event_type": "PRIORITY_CHANGED"},
            {"time": now_time, "event": "DISPATCH_CREATED: Multi-agency response orchestrator triggered: Hospital Trauma + Fire Engine + Highway Patrol.", "event_type": "DISPATCH_CREATED"}
        ]
        
        simulated_inc = {
            "incident_id": "CAM01_001",
            "type": "collision",
            "camera_id": "CAM-01",
            "location": {"name": "NH-44, KM 124", "lat": 17.385, "lon": 78.4867},
            "timestamp": now_time,
            "features": features,
            "severity_score": score,
            "severity_label": label,
            "severity_factors": factors,
            "response_workflow": "hospital+fire+police",
            "timeline": timeline_events,
            "status": "active"
        }
        
        # Save incident & orchestrate dispatches
        store.upsert_incident(simulated_inc)
        orchestrator.reprioritize_all_incidents()
        orchestrator.orchestrate_dispatches_for_incident("CAM01_001")
        
        # Generate evidence-grounded report
        full_inc = store.get_incident("CAM01_001")
        full_inc["report"] = orchestrator.generate_report(full_inc)
        store.upsert_incident(full_inc)
        
        return {
            "scenario": "collision_escalation",
            "status": "success",
            "incident": store.get_incident("CAM01_001"),
            "dispatches": store.get_dispatches_for_incident("CAM01_001")
        }

    elif scenario_name == "rollover_multiagency":
        # Scenario B: High-Severity Vehicle Rollover on CAM02_004
        features = {
            "vehicle_count": 2,
            "person_on_road": True,
            "fire_smoke": True,
            "rollover": True,
            "traffic_impact": "critical",
            "lane_blockage": 2,
            "confidence": 0.96
        }
        score, label, factors = orchestrator.calculate_severity(features, "rollover")
        
        timeline_events = [
            {"time": now_time, "event": "DETECTION_RECEIVED: Flyover camera CAM-02 confirmed rollover with secondary impact.", "event_type": "DETECTION_RECEIVED"},
            {"time": now_time, "event": f"SEVERITY_RECALCULATED: Rollover severity elevated to {score}/100 ({label.upper()}).", "event_type": "SEVERITY_RECALCULATED"},
            {"time": now_time, "event": "DISPATCH_CREATED: Tier-1 trauma medical + heavy recovery crane dispatched.", "event_type": "DISPATCH_CREATED"}
        ]
        
        simulated_inc = {
            "incident_id": "CAM02_004",
            "type": "rollover",
            "camera_id": "CAM-02",
            "location": {"name": "Inner Ring Road, Junction 8", "lat": 17.412, "lon": 78.448},
            "timestamp": now_time,
            "features": features,
            "severity_score": score,
            "severity_label": label,
            "severity_factors": factors,
            "response_workflow": "hospital+fire+towing",
            "timeline": timeline_events,
            "status": "active"
        }
        
        store.upsert_incident(simulated_inc)
        orchestrator.reprioritize_all_incidents()
        orchestrator.orchestrate_dispatches_for_incident("CAM02_004")
        
        full_inc = store.get_incident("CAM02_004")
        full_inc["report"] = orchestrator.generate_report(full_inc)
        store.upsert_incident(full_inc)
        
        return {
            "scenario": "rollover_multiagency",
            "status": "success",
            "incident": store.get_incident("CAM02_004")
        }

    elif scenario_name == "safewatch_anomaly":
        # Scenario C: SafeWatch Public Safety Anomaly
        evt = {
            "event_id": f"SAFE-06_{int(datetime.now().timestamp()) % 1000}",
            "event_type": "POTENTIAL_SAFETY_ANOMALY",
            "camera_id": "CAM-06",
            "location": {"name": "Gachibowli Underpass South", "lat": 17.442, "lon": 78.348},
            "timestamp": now_time,
            "confidence": 0.93,
            "observed_signals": [
                "Sudden movement pursuit pattern detected near isolated walkway",
                "Prolonged clustering around pedestrian corridor",
                "Restricted visibility lighting conditions"
            ],
            "risk_level": "CRITICAL",
            "human_review_required": True,
            "status": "PENDING_REVIEW",
            "recommended_response": "AUTHORIZED PATROL / WOMEN'S SAFETY RESPONSE ADVISORY",
            "approved_by": None,
            "approval_timestamp": None,
            "simulated_alert_sent": False,
            "timeline": [
                {"time": now_time, "event": "DETECTION_RECEIVED: Camera CAM-06 tracked unusual movement convergence in underpass.", "event_type": "DETECTION_RECEIVED"},
                {"time": now_time, "event": "POTENTIAL_SAFETY_ANOMALY: Spatial safety risk model flagged potential vulnerable-person safety event.", "event_type": "OBSERVATION_UPDATED"},
                {"time": now_time, "event": "HUMAN_REVIEW_REQUIRED: Operator review required before dispatching simulated alert.", "event_type": "HUMAN_REVIEW_REQUIRED"}
            ]
        }
        store.upsert_safewatch_event(evt)
        return {
            "scenario": "safewatch_anomaly",
            "status": "success",
            "event": evt
        }
    else:
        raise HTTPException(status_code=400, detail=f"Unknown scenario: {scenario_name}")

@app.post("/reset")
def reset_demo_state():
    store.seed_baseline_data()
    orchestrator.reprioritize_all_incidents()
    return {
        "status": "ok",
        "message": "Demo baseline dataset successfully restored",
        "incidents_count": len(store.get_all_incidents()),
        "dispatches_count": len(store.get_all_dispatches()),
        "safewatch_count": len(store.get_all_safewatch_events())
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
