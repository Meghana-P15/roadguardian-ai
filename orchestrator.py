from typing import Dict, Any, List, Tuple
from datetime import datetime
import store

def calculate_severity(features: Dict[str, Any], incident_type: str = "collision") -> Tuple[int, str, Dict[str, Any]]:
    base_scores = {
        "collision": 40,
        "rollover": 60,
        "fire": 70,
        "stalled_vehicle": 35,
        "debris": 25,
        "safewatch_anomaly": 50
    }
    
    base_score = base_scores.get(incident_type.lower(), 40)
    score = base_score
    factors = []
    factor_breakdown = {f"base_{incident_type}": base_score}
    
    # Structured feature weight contributions
    if features.get("person_on_road"):
        score += 25
        factors.append("Person / Pedestrian on active roadway (+25 pts)")
        factor_breakdown["person_on_road"] = 25
        
    if features.get("fire_smoke"):
        score += 20
        factors.append("Active thermal combustion / smoke plume (+20 pts)")
        factor_breakdown["fire_smoke"] = 20
        
    if features.get("rollover"):
        score += 15
        factors.append("Overturned vehicle / rollover confirmed (+15 pts)")
        factor_breakdown["rollover"] = 15
        
    v_count = features.get("vehicle_count", 1)
    if v_count > 1:
        v_pts = min(v_count * 5, 20)
        score += v_pts
        factors.append(f"Multi-vehicle pileup ({v_count} vehicles involved, +{v_pts} pts)")
        factor_breakdown["multi_vehicle"] = v_pts
        
    traffic = features.get("traffic_impact", "low")
    if traffic == "critical":
        score += 15
        factors.append("Critical traffic blockage extending > 1.5km (+15 pts)")
        factor_breakdown["traffic_impact_critical"] = 15
    elif traffic == "high":
        score += 10
        factors.append("Heavy corridor congestion (+10 pts)")
        factor_breakdown["traffic_impact_high"] = 10
    elif traffic == "medium":
        score += 5
        factors.append("Moderate lane slowdown (+5 pts)")
        factor_breakdown["traffic_impact_medium"] = 5
        
    score = max(10, min(100, score))
    
    if score >= 85:
        label = "Critical"
    elif score >= 65:
        label = "High"
    elif score >= 45:
        label = "Medium"
    else:
        label = "Low"
        
    severity_factors = {
        "base_score": base_score,
        "factors": factors,
        "factor_breakdown": factor_breakdown
    }
        
    return score, label, severity_factors

def pick_response_workflow(features: Dict[str, Any], severity_label: str, incident_type: str) -> str:
    has_fire = features.get("fire_smoke", False)
    has_pedestrian = features.get("person_on_road", False)
    has_rollover = features.get("rollover", False)
    
    if has_fire and has_pedestrian:
        return "hospital+fire+police"
    if has_fire:
        return "fire+police"
    if has_pedestrian or severity_label == "Critical":
        return "hospital+police"
    if has_rollover:
        return "hospital+towing"
    return "police"

def reprioritize_all_incidents() -> List[Dict[str, Any]]:
    incidents = store.get_all_incidents()
    
    # Priority ranking metric considering severity, life hazard, and traffic impact
    def get_priority_metric(inc):
        f = inc.get("features", {})
        score = inc.get("severity_score", 0)
        risk_weight = 0
        if f.get("person_on_road"): risk_weight += 30
        if f.get("fire_smoke"): risk_weight += 25
        if f.get("rollover"): risk_weight += 20
        if f.get("traffic_impact") == "critical": risk_weight += 15
        return score * 1.0 + risk_weight

    incidents.sort(key=get_priority_metric, reverse=True)
    
    rank_map = {}
    explanations = {}
    for idx, inc in enumerate(incidents):
        rank = idx + 1
        inc["priority_rank"] = rank
        inc_id = inc["incident_id"]
        rank_map[inc_id] = rank
        
        f = inc.get("features", {})
        score = inc.get("severity_score", 0)
        label = inc.get("severity_label", "Medium")
        
        if rank == 1:
            reasons = []
            if f.get("person_on_road"): reasons.append("active pedestrian hazard")
            if f.get("fire_smoke"): reasons.append("thermal fire plume")
            if f.get("rollover"): reasons.append("overturned vehicle")
            if f.get("vehicle_count", 1) > 1: reasons.append(f"{f.get('vehicle_count')} vehicle pileup")
            reason_str = ", ".join(reasons) if reasons else "highest severity hazard"
            explanations[inc_id] = f"Rank #1: Critical lethality index ({score}/100) driven by {reason_str}."
        elif rank == 2:
            explanations[inc_id] = f"Rank #2: High priority ({score}/100) secondary to priority #1 active life hazards."
        else:
            explanations[inc_id] = f"Rank #{rank}: Lower relative urgency ({score}/100) with contained road corridor delay."

    store.update_priority_ranks(rank_map, explanations)
    return store.get_all_incidents()

def orchestrate_dispatches_for_incident(incident_id: str) -> List[Dict[str, Any]]:
    inc = store.get_incident(incident_id)
    if not inc:
        return []

    f = inc.get("features", {})
    workflow = inc.get("response_workflow", "police")
    now_time = datetime.now().strftime("%H:%M:%S")
    
    created_dispatches = []
    
    # 1. Hospital Ambulance
    if "hospital" in workflow or f.get("person_on_road") or inc.get("severity_label") == "Critical":
        disp_med = {
            "dispatch_id": f"DISP-{incident_id}-MED",
            "incident_id": incident_id,
            "unit_type": "AMBULANCE",
            "unit_id": "MED-04 (Trauma I)",
            "station": "City General Hospital Trauma Wing",
            "distance_km": 3.2,
            "eta_minutes": 4.2,
            "status": "EN_ROUTE",
            "history": [
                {"time": now_time, "status": "ALERT_SENT"},
                {"time": now_time, "status": "ACKNOWLEDGED"},
                {"time": now_time, "status": "EN_ROUTE"}
            ]
        }
        store.upsert_dispatch(disp_med)
        created_dispatches.append(disp_med)
        
        store.add_delivery_log({
            "log_id": f"LOG-{incident_id}-MED",
            "dispatch_id": disp_med["dispatch_id"],
            "recipient_type": "HOSPITAL_EMS",
            "unit_type": "AMBULANCE",
            "message_summary": f"SIMULATED DISPATCH: Automated alert for {incident_id} at {inc.get('location', {}).get('name')}. Trauma Paramedics dispatched.",
            "delivery_status": "SIMULATED ALERT DELIVERED",
            "timestamp": now_time
        })

    # 2. Fire & Rescue
    if "fire" in workflow or f.get("fire_smoke"):
        disp_fire = {
            "dispatch_id": f"DISP-{incident_id}-FIRE",
            "incident_id": incident_id,
            "unit_type": "FIRE_RESCUE",
            "unit_id": "ENGINE-12",
            "station": "Sector 5 Heavy Fire HQ",
            "distance_km": 2.8,
            "eta_minutes": 3.8,
            "status": "EN_ROUTE",
            "history": [
                {"time": now_time, "status": "ALERT_SENT"},
                {"time": now_time, "status": "ACKNOWLEDGED"},
                {"time": now_time, "status": "EN_ROUTE"}
            ]
        }
        store.upsert_dispatch(disp_fire)
        created_dispatches.append(disp_fire)
        
        store.add_delivery_log({
            "log_id": f"LOG-{incident_id}-FIRE",
            "dispatch_id": disp_fire["dispatch_id"],
            "recipient_type": "FIRE_CONTROL",
            "unit_type": "FIRE_RESCUE",
            "message_summary": f"SIMULATED DISPATCH: Active thermal fire combustion confirmed at {inc.get('location', {}).get('name')}. Heavy rescue response en route.",
            "delivery_status": "SIMULATED ALERT DELIVERED",
            "timestamp": now_time
        })

    # 3. Police / Highway Patrol
    disp_police = {
        "dispatch_id": f"DISP-{incident_id}-POLICE",
        "incident_id": incident_id,
        "unit_type": "HIGHWAY_PATROL",
        "unit_id": "PATROL-09",
        "station": "NH-44 Expressway Patrol Post",
        "distance_km": 1.5,
        "eta_minutes": 2.1,
        "status": "EN_ROUTE",
        "history": [
            {"time": now_time, "status": "ALERT_SENT"},
            {"time": now_time, "status": "ACKNOWLEDGED"},
            {"time": now_time, "status": "EN_ROUTE"}
        ]
    }
    store.upsert_dispatch(disp_police)
    created_dispatches.append(disp_police)
    
    store.add_delivery_log({
        "log_id": f"LOG-{incident_id}-POLICE",
        "dispatch_id": disp_police["dispatch_id"],
        "recipient_type": "POLICE_DISPATCH",
        "unit_type": "HIGHWAY_PATROL",
        "message_summary": f"SIMULATED DISPATCH: Highway intervention team assigned to secure perimeter and redirect expressway traffic at {inc.get('location', {}).get('name')}.",
        "delivery_status": "SIMULATED ALERT DELIVERED",
        "timestamp": now_time
    })

    return created_dispatches

def generate_report(incident: Dict[str, Any]) -> str:
    inc_id = incident.get("incident_id", "UNKNOWN")
    inc_type = incident.get("type", "incident").upper()
    loc_name = incident.get("location", {}).get("name", "Expressway Monitored Zone")
    lat = incident.get("location", {}).get("lat", 0.0)
    lon = incident.get("location", {}).get("lon", 0.0)
    time_str = incident.get("timestamp", "NOW")
    score = incident.get("severity_score", 50)
    label = incident.get("severity_label", "Medium")
    rank = incident.get("priority_rank", 1)
    workflow = incident.get("response_workflow", "police").upper()
    
    f = incident.get("features", {})
    v_count = f.get("vehicle_count", 1)
    ped = "[DETECTED] Person on active travel lanes" if f.get("person_on_road") else "[CLEAR] No pedestrian on active roadway"
    fire = "[ACTIVE] Thermal combustion / fire plume confirmed" if f.get("fire_smoke") else "[CLEAR] Thermal scan clean"
    roll = "[CONFIRMED] Vehicle rollover / overturned" if f.get("rollover") else "[NORMAL] Vehicle upright"
    traffic = f.get("traffic_impact", "low").upper()
    lanes = f.get("lane_blockage", 1)
    
    dispatches = incident.get("dispatches", [])
    disp_summary = []
    if dispatches:
        for d in dispatches:
            disp_summary.append(f"- {d.get('unit_type')}: {d.get('unit_id')} ({d.get('station')}) | Status: {d.get('status')} | ETA: {d.get('eta_minutes')}m")
    else:
        disp_summary = [f"- Protocol Active: [{workflow}] (Simulated Alert Sent to Coordination Grid)"]
    
    disp_text = "\n".join(disp_summary)
    
    return f"""====================================================
ROADGUARDIAN AI — EVIDENCE-GROUNDED INCIDENT DOSSIER
====================================================

INCIDENT ID: {inc_id}
INCIDENT TYPE: {inc_type}
LOCATION: {loc_name} (Coordinates: {lat}° N, {lon}° E)
TIMESTAMP: {time_str} IST
CURRENT STATUS: {incident.get('status', 'ACTIVE').upper()}

[1] STRUCTURED OBSERVATIONS (OBSERVED FACT):
- Involved Vehicles: {v_count} unit(s) tracked by camera AI.
- Lane Blockage: {lanes} travel lane(s) obstructed.
- Pedestrian / Road Hazard: {ped}
- Thermal / Combustion Signature: {fire}
- Vehicle Attitude / Orientation: {roll}
- Expressway Traffic Impact: {traffic}

[2] SEVERITY ASSESSMENT (CALCULATED SCORE):
- AI Severity Score: {score}/100 ({label.upper()})
- Confidence Level: {int(f.get('confidence', 0.92) * 100)}% Multi-Spectral Ingestion
- Contributing Risk Factors: {', '.join(incident.get('severity_factors', {}).get('factors', ['Observation matrix'])) if incident.get('severity_factors') else 'Composite telemetry'}

[3] PRIORITY EXPLANATION (GLOBAL QUEUE POSITION):
- Current Queue Priority: PRIORITY #{rank}
- Justification: {incident.get('why_priority_explanation', 'Evaluated against all concurrent monitored expressway nodes.')}

[4] RECOMMENDED RESPONSE (AI RECOMMENDATION):
- Required Multi-Agency Workflow: [{workflow}]
- Protocol Triggers: High lethality reduction & immediate lane clearance.

[5] DISPATCH STATUS (SIMULATED ACTION):
{disp_text}

[6] EVIDENCE SUMMARY:
- Camera Source: {incident.get('camera_id', 'CAM-01')}
- Video Clip: {incident.get('evidence', {}).get('clip_path', 'evidence/CAM01_001/clip.mp4')}
- Registered Keyframes: {len(incident.get('evidence', {}).get('key_frames', []))} high-resolution CCTV captures.

[7] EVENT TIMELINE SUMMARY:
- Ingestion, multi-spectral observation, severity re-calculation, and response dispatch logged in audit trail.

[8] UNKNOWN OR UNVERIFIED INFORMATION:
- Occupant triage count pending on-scene paramedic confirmation."""
