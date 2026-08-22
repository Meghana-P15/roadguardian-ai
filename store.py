import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "roadguardian.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Incidents Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS incidents (
        incident_id TEXT PRIMARY KEY,
        type TEXT,
        camera_id TEXT,
        location_json TEXT,
        features_json TEXT,
        severity_score INTEGER,
        severity_label TEXT,
        priority_rank INTEGER,
        status TEXT,
        evidence_json TEXT,
        timeline_json TEXT,
        report TEXT,
        response_workflow TEXT,
        severity_factors_json TEXT,
        why_priority_explanation TEXT,
        timestamp TEXT,
        created_at TEXT,
        updated_at TEXT
    );
    """)

    # Migrate columns if old table exists
    cursor.execute("PRAGMA table_info(incidents)")
    existing_cols = {row["name"] for row in cursor.fetchall()}
    if "severity_factors_json" not in existing_cols:
        cursor.execute("ALTER TABLE incidents ADD COLUMN severity_factors_json TEXT")
    if "why_priority_explanation" not in existing_cols:
        cursor.execute("ALTER TABLE incidents ADD COLUMN why_priority_explanation TEXT")

    # 2. Dispatches Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dispatches (
        dispatch_id TEXT PRIMARY KEY,
        incident_id TEXT,
        unit_type TEXT,
        unit_id TEXT,
        station TEXT,
        distance_km REAL,
        eta_minutes REAL,
        status TEXT,
        history_json TEXT,
        created_at TEXT,
        updated_at TEXT
    );
    """)

    # 3. Alert Delivery Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS delivery_logs (
        log_id TEXT PRIMARY KEY,
        dispatch_id TEXT,
        recipient_type TEXT,
        unit_type TEXT,
        message_summary TEXT,
        delivery_status TEXT,
        timestamp TEXT
    );
    """)

    # 4. SafeWatch Events Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS safewatch_events (
        event_id TEXT PRIMARY KEY,
        event_type TEXT,
        camera_id TEXT,
        location_json TEXT,
        timestamp TEXT,
        confidence REAL,
        observed_signals_json TEXT,
        risk_level TEXT,
        human_review_required INTEGER,
        status TEXT,
        recommended_response TEXT,
        approved_by TEXT,
        approval_timestamp TEXT,
        simulated_alert_sent INTEGER,
        timeline_json TEXT,
        created_at TEXT,
        updated_at TEXT
    );
    """)

    conn.commit()
    conn.close()

# ==========================================
# Incidents Store
# ==========================================

def deserialize_incident(row: sqlite3.Row) -> Dict[str, Any]:
    incident_id = row["incident_id"]
    dispatches = get_dispatches_for_incident(incident_id)
    
    return {
        "incident_id": row["incident_id"],
        "type": row["type"],
        "camera_id": row["camera_id"],
        "location": json.loads(row["location_json"] or "{}"),
        "features": json.loads(row["features_json"] or "{}"),
        "severity_score": row["severity_score"],
        "severity_label": row["severity_label"],
        "priority_rank": row["priority_rank"],
        "status": row["status"],
        "evidence": json.loads(row["evidence_json"] or "{}"),
        "timeline": json.loads(row["timeline_json"] or "[]"),
        "report": row["report"] or "",
        "response_workflow": row["response_workflow"] or "police",
        "severity_factors": json.loads(row["severity_factors_json"] or "null") if "severity_factors_json" in row.keys() and row["severity_factors_json"] else None,
        "why_priority_explanation": row["why_priority_explanation"] if "why_priority_explanation" in row.keys() else None,
        "timestamp": row["timestamp"] or "",
        "dispatches": dispatches
    }

def get_all_incidents() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM incidents ORDER BY priority_rank ASC")
    rows = cursor.fetchall()
    conn.close()
    return [deserialize_incident(r) for r in rows]

def get_incident(incident_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM incidents WHERE incident_id = ?", (incident_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return deserialize_incident(row)
    return None

def upsert_incident(inc: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.utcnow().isoformat()

    existing = get_incident(inc["incident_id"])
    if existing:
        merged_features = {**existing.get("features", {}), **inc.get("features", {})}
        merged_timeline = existing.get("timeline", [])
        if inc.get("timeline"):
            # Avoid duplicate timeline events by event text
            existing_events = {t.get("event") for t in merged_timeline}
            for t in inc["timeline"]:
                if t.get("event") not in existing_events:
                    merged_timeline.append(t)
        merged_evidence = {**existing.get("evidence", {}), **inc.get("evidence", {})}

        cursor.execute("""
            UPDATE incidents SET
                type = ?,
                camera_id = ?,
                location_json = ?,
                features_json = ?,
                severity_score = ?,
                severity_label = ?,
                priority_rank = ?,
                status = ?,
                evidence_json = ?,
                timeline_json = ?,
                report = ?,
                response_workflow = ?,
                severity_factors_json = ?,
                why_priority_explanation = ?,
                timestamp = ?,
                updated_at = ?
            WHERE incident_id = ?
        """, (
            inc.get("type", existing["type"]),
            inc.get("camera_id", existing["camera_id"]),
            json.dumps(inc.get("location", existing["location"])),
            json.dumps(merged_features),
            inc.get("severity_score", existing["severity_score"]),
            inc.get("severity_label", existing["severity_label"]),
            inc.get("priority_rank", existing["priority_rank"]),
            inc.get("status", existing["status"]),
            json.dumps(merged_evidence),
            json.dumps(merged_timeline),
            inc.get("report", existing["report"]),
            inc.get("response_workflow", existing["response_workflow"]),
            json.dumps(inc.get("severity_factors", existing.get("severity_factors"))),
            inc.get("why_priority_explanation", existing.get("why_priority_explanation")),
            inc.get("timestamp", existing["timestamp"]),
            now_str,
            inc["incident_id"]
        ))
    else:
        cursor.execute("""
            INSERT INTO incidents (
                incident_id, type, camera_id, location_json, features_json,
                severity_score, severity_label, priority_rank, status,
                evidence_json, timeline_json, report, response_workflow,
                severity_factors_json, why_priority_explanation,
                timestamp, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            inc["incident_id"],
            inc.get("type", "collision"),
            inc.get("camera_id", "CAM-01"),
            json.dumps(inc.get("location", {})),
            json.dumps(inc.get("features", {})),
            inc.get("severity_score", 50),
            inc.get("severity_label", "Medium"),
            inc.get("priority_rank", 99),
            inc.get("status", "active"),
            json.dumps(inc.get("evidence", {})),
            json.dumps(inc.get("timeline", [])),
            inc.get("report", ""),
            inc.get("response_workflow", "police"),
            json.dumps(inc.get("severity_factors")),
            inc.get("why_priority_explanation", ""),
            inc.get("timestamp", now_str),
            now_str,
            now_str
        ))

    conn.commit()
    conn.close()
    return get_incident(inc["incident_id"])

def update_priority_ranks(rank_map: Dict[str, int], explanations: Dict[str, str]):
    conn = get_connection()
    cursor = conn.cursor()
    for inc_id, rank in rank_map.items():
        expl = explanations.get(inc_id, "")
        cursor.execute("UPDATE incidents SET priority_rank = ?, why_priority_explanation = ? WHERE incident_id = ?", (rank, expl, inc_id))
    conn.commit()
    conn.close()

# ==========================================
# Dispatches & Delivery Logs Store
# ==========================================

def deserialize_dispatch(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "dispatch_id": row["dispatch_id"],
        "incident_id": row["incident_id"],
        "unit_type": row["unit_type"],
        "unit_id": row["unit_id"],
        "station": row["station"],
        "distance_km": row["distance_km"],
        "eta_minutes": row["eta_minutes"],
        "status": row["status"],
        "history": json.loads(row["history_json"] or "[]"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

def get_all_dispatches() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dispatches ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [deserialize_dispatch(r) for r in rows]

def get_dispatches_for_incident(incident_id: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dispatches WHERE incident_id = ? ORDER BY created_at ASC", (incident_id,))
    rows = cursor.fetchall()
    conn.close()
    return [deserialize_dispatch(r) for r in rows]

def get_dispatch(dispatch_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dispatches WHERE dispatch_id = ?", (dispatch_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return deserialize_dispatch(row)
    return None

def upsert_dispatch(disp: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.utcnow().isoformat()

    existing = get_dispatch(disp["dispatch_id"])
    if existing:
        cursor.execute("""
            UPDATE dispatches SET
                unit_type = ?,
                unit_id = ?,
                station = ?,
                distance_km = ?,
                eta_minutes = ?,
                status = ?,
                history_json = ?,
                updated_at = ?
            WHERE dispatch_id = ?
        """, (
            disp.get("unit_type", existing["unit_type"]),
            disp.get("unit_id", existing["unit_id"]),
            disp.get("station", existing["station"]),
            disp.get("distance_km", existing["distance_km"]),
            disp.get("eta_minutes", existing["eta_minutes"]),
            disp.get("status", existing["status"]),
            json.dumps(disp.get("history", existing["history"])),
            now_str,
            disp["dispatch_id"]
        ))
    else:
        cursor.execute("""
            INSERT INTO dispatches (
                dispatch_id, incident_id, unit_type, unit_id, station,
                distance_km, eta_minutes, status, history_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            disp["dispatch_id"],
            disp["incident_id"],
            disp.get("unit_type", "AMBULANCE"),
            disp.get("unit_id", "UNIT-01"),
            disp.get("station", "General Base"),
            disp.get("distance_km", 2.5),
            disp.get("eta_minutes", 4.0),
            disp.get("status", "ALERT_SENT"),
            json.dumps(disp.get("history", [{"time": now_str, "status": "ALERT_SENT"}])),
            now_str,
            now_str
        ))
    conn.commit()
    conn.close()
    return get_dispatch(disp["dispatch_id"])

def update_dispatch_status(dispatch_id: str, new_status: str) -> Optional[Dict[str, Any]]:
    disp = get_dispatch(dispatch_id)
    if not disp:
        return None
    
    now_time = datetime.now().strftime("%H:%M:%S")
    history = disp.get("history", [])
    history.append({"time": now_time, "status": new_status})
    
    disp["status"] = new_status
    disp["history"] = history
    return upsert_dispatch(disp)

def get_all_delivery_logs() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM delivery_logs ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_delivery_log(log: Dict[str, Any]):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO delivery_logs (
            log_id, dispatch_id, recipient_type, unit_type,
            message_summary, delivery_status, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        log["log_id"],
        log.get("dispatch_id", ""),
        log.get("recipient_type", "EMERGENCY_DISPATCH"),
        log.get("unit_type", ""),
        log.get("message_summary", ""),
        log.get("delivery_status", "SIMULATED ALERT DELIVERED"),
        log.get("timestamp", datetime.now().strftime("%H:%M:%S"))
    ))
    conn.commit()
    conn.close()

# ==========================================
# SafeWatch Events Store
# ==========================================

def deserialize_safewatch(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "event_id": row["event_id"],
        "event_type": row["event_type"],
        "camera_id": row["camera_id"],
        "location": json.loads(row["location_json"] or "{}"),
        "timestamp": row["timestamp"],
        "confidence": row["confidence"],
        "observed_signals": json.loads(row["observed_signals_json"] or "[]"),
        "risk_level": row["risk_level"],
        "human_review_required": bool(row["human_review_required"]),
        "status": row["status"],
        "recommended_response": row["recommended_response"],
        "approved_by": row["approved_by"],
        "approval_timestamp": row["approval_timestamp"],
        "simulated_alert_sent": bool(row["simulated_alert_sent"]),
        "timeline": json.loads(row["timeline_json"] or "[]")
    }

def get_all_safewatch_events() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM safewatch_events ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    return [deserialize_safewatch(r) for r in rows]

def get_safewatch_event(event_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM safewatch_events WHERE event_id = ?", (event_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return deserialize_safewatch(row)
    return None

def upsert_safewatch_event(evt: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.utcnow().isoformat()

    existing = get_safewatch_event(evt["event_id"])
    if existing:
        cursor.execute("""
            UPDATE safewatch_events SET
                event_type = ?,
                camera_id = ?,
                location_json = ?,
                timestamp = ?,
                confidence = ?,
                observed_signals_json = ?,
                risk_level = ?,
                human_review_required = ?,
                status = ?,
                recommended_response = ?,
                approved_by = ?,
                approval_timestamp = ?,
                simulated_alert_sent = ?,
                timeline_json = ?,
                updated_at = ?
            WHERE event_id = ?
        """, (
            evt.get("event_type", existing["event_type"]),
            evt.get("camera_id", existing["camera_id"]),
            json.dumps(evt.get("location", existing["location"])),
            evt.get("timestamp", existing["timestamp"]),
            evt.get("confidence", existing["confidence"]),
            json.dumps(evt.get("observed_signals", existing["observed_signals"])),
            evt.get("risk_level", existing["risk_level"]),
            1 if evt.get("human_review_required", existing["human_review_required"]) else 0,
            evt.get("status", existing["status"]),
            evt.get("recommended_response", existing["recommended_response"]),
            evt.get("approved_by", existing["approved_by"]),
            evt.get("approval_timestamp", existing["approval_timestamp"]),
            1 if evt.get("simulated_alert_sent", existing["simulated_alert_sent"]) else 0,
            json.dumps(evt.get("timeline", existing["timeline"])),
            now_str,
            evt["event_id"]
        ))
    else:
        cursor.execute("""
            INSERT INTO safewatch_events (
                event_id, event_type, camera_id, location_json, timestamp,
                confidence, observed_signals_json, risk_level, human_review_required,
                status, recommended_response, approved_by, approval_timestamp,
                simulated_alert_sent, timeline_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            evt["event_id"],
            evt.get("event_type", "POTENTIAL_SAFETY_ANOMALY"),
            evt.get("camera_id", "CAM-06"),
            json.dumps(evt.get("location", {})),
            evt.get("timestamp", datetime.now().strftime("%H:%M:%S")),
            evt.get("confidence", 0.88),
            json.dumps(evt.get("observed_signals", [])),
            evt.get("risk_level", "HIGH"),
            1 if evt.get("human_review_required", True) else 0,
            evt.get("status", "PENDING_REVIEW"),
            evt.get("recommended_response", "AUTHORIZED_PATROL"),
            evt.get("approved_by"),
            evt.get("approval_timestamp"),
            1 if evt.get("simulated_alert_sent", False) else 0,
            json.dumps(evt.get("timeline", [])),
            now_str,
            now_str
        ))
    conn.commit()
    conn.close()
    return get_safewatch_event(evt["event_id"])

# ==========================================
# Baseline Seeding
# ==========================================

def seed_baseline_data():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM incidents")
    cursor.execute("DELETE FROM dispatches")
    cursor.execute("DELETE FROM delivery_logs")
    cursor.execute("DELETE FROM safewatch_events")
    conn.commit()
    conn.close()

    now_time = datetime.now().strftime("%H:%M:%S")

    # Baseline incidents
    baseline_incidents = [
        {
            "incident_id": "CAM01_001",
            "type": "collision",
            "camera_id": "CAM-01",
            "location": {"name": "NH-44, KM 124", "lat": 17.385, "lon": 78.4867},
            "timestamp": "14:32:10",
            "features": {
                "vehicle_count": 1,
                "person_on_road": False,
                "fire_smoke": False,
                "rollover": False,
                "traffic_impact": "low",
                "lane_blockage": 0,
                "confidence": 0.91
            },
            "severity_score": 45,
            "severity_label": "Low",
            "priority_rank": 3,
            "status": "active",
            "severity_factors": {
                "base_score": 40,
                "factors": ["Single vehicle stationary near shoulder (+5 pts)"],
                "factor_breakdown": {"base_collision": 40, "vehicle_count": 5}
            },
            "why_priority_explanation": "Single stationary vehicle on shoulder with minimal traffic delay; low lethality risk.",
            "evidence": {
                "clip_path": "evidence/CAM01_001/clip.mp4",
                "key_frames": ["https://images.unsplash.com/photo-1543465077-db45d34b88a5?q=80&w=800&auto=format&fit=crop"]
            },
            "timeline": [
                {"time": "14:32:10", "event": "DETECTION_RECEIVED: Camera CAM-01 logged minor contact near median strip.", "event_type": "DETECTION_RECEIVED"},
                {"time": "14:32:15", "event": "OBSERVATION_UPDATED: Single vehicle tracking on shoulder.", "event_type": "OBSERVATION_UPDATED"},
                {"time": "14:32:20", "event": "SEVERITY_RECALCULATED: Baseline severity score assessed at 45/100 (Low).", "event_type": "SEVERITY_RECALCULATED"},
                {"time": "14:32:25", "event": "PRIORITY_CHANGED: Queued at Priority Rank #3.", "event_type": "PRIORITY_CHANGED"}
            ],
            "report": """INCIDENT ID: CAM01_001
INCIDENT TYPE: COLLISION (MINOR SHOULDER CONTACT)
LOCATION: NH-44, KM 124 (Lat: 17.385, Lon: 78.4867)
TIMESTAMP: 14:32:10 IST
CURRENT STATUS: ACTIVE MONITORING

STRUCTURED OBSERVATIONS:
- 1 vehicle stationary near expressway median.
- Pedestrian / Person on road: None detected on active travel lanes.
- Fire / Thermal Plume: Thermal scanner clean (no combustion).
- Orientation: Vehicle upright on shoulder.
- Traffic Impact: Low (flow maintained).

SEVERITY ASSESSMENT:
- Calculated Score: 45/100 (Low Severity)
- Confidence: 91%

PRIORITY EXPLANATION:
- Current Priority Rank: #3 (Subordinate to flyover rollover CAM02_004).

RECOMMENDED RESPONSE:
- Highway Patrol Routine Monitor.

DISPATCH STATUS:
- Highway Patrol #09 on Standby.

EVIDENCE SUMMARY:
- Camera CAM-01 Frame #1482 keyframe registered.

EVENT TIMELINE SUMMARY:
- 14:32:10 Initial vehicle tracking.

UNKNOWN OR UNVERIFIED INFORMATION:
- Vehicle driveability unconfirmed.""",
            "response_workflow": "police"
        },
        {
            "incident_id": "CAM02_004",
            "type": "rollover",
            "camera_id": "CAM-02",
            "location": {"name": "Inner Ring Road, Junction 8", "lat": 17.412, "lon": 78.448},
            "timestamp": "14:35:42",
            "features": {
                "vehicle_count": 1,
                "person_on_road": False,
                "fire_smoke": False,
                "rollover": True,
                "traffic_impact": "high",
                "lane_blockage": 2,
                "confidence": 0.94
            },
            "severity_score": 82,
            "severity_label": "High",
            "priority_rank": 1,
            "status": "active",
            "severity_factors": {
                "base_score": 60,
                "factors": ["Rollover vehicle overturned (+15 pts)", "High traffic impact blocking 2 lanes (+10 pts)"],
                "factor_breakdown": {"base_rollover": 60, "rollover": 15, "traffic_impact": 10}
            },
            "why_priority_explanation": "Vehicle overturned on flyover ramp blocking 2 lanes; high traffic hazard.",
            "evidence": {
                "clip_path": "evidence/CAM02_004/clip.mp4",
                "key_frames": ["https://images.unsplash.com/photo-1508974239320-0a029497e820?q=80&w=800&auto=format&fit=crop"]
            },
            "timeline": [
                {"time": "14:35:42", "event": "DETECTION_RECEIVED: Single vehicle rollover detected on flyover ramp.", "event_type": "DETECTION_RECEIVED"},
                {"time": "14:35:50", "event": "SEVERITY_RECALCULATED: Severity score evaluated at 82/100 (High).", "event_type": "SEVERITY_RECALCULATED"},
                {"time": "14:36:00", "event": "PRIORITY_CHANGED: Elevated to Priority #1.", "event_type": "PRIORITY_CHANGED"},
                {"time": "14:36:05", "event": "DISPATCH_CREATED: Medical & Tow recovery alert sent.", "event_type": "DISPATCH_CREATED"}
            ],
            "report": """INCIDENT ID: CAM02_004
INCIDENT TYPE: VEHICLE ROLLOVER
LOCATION: Inner Ring Road, Junction 8 (Lat: 17.412, Lon: 78.448)
TIMESTAMP: 14:35:42 IST
CURRENT STATUS: ACTIVE RESPONSE

STRUCTURED OBSERVATIONS:
- 1 SUV overturned on driver side.
- Pedestrian on road: Clear.
- Fire/Smoke: Negative.
- Traffic Impact: High (blocking lanes 1 & 2).

SEVERITY ASSESSMENT:
- Calculated Score: 82/100 (High Severity)
- Confidence: 94%

PRIORITY EXPLANATION:
- Current Priority: #1 due to multi-lane flyover blockage.

RECOMMENDED RESPONSE:
- Medical Paramedic + Heavy Tow Crane Recovery.

DISPATCH STATUS:
- Paramedic Unit #02 Dispatched (ETA 5.1m).
- Heavy Tow #05 Dispatched (ETA 7.0m).

EVIDENCE SUMMARY:
- CCTV keyframe recorded from CAM-02.

EVENT TIMELINE SUMMARY:
- 14:35:42 Rollover detected; 14:36:05 Dispatch sent.

UNKNOWN OR UNVERIFIED INFORMATION:
- Occupant injury count unconfirmed.""",
            "response_workflow": "hospital+towing"
        },
        {
            "incident_id": "CAM03_012",
            "type": "stalled_vehicle",
            "camera_id": "CAM-03",
            "location": {"name": "ORR KM 45, Exit 6", "lat": 17.456, "lon": 78.372},
            "timestamp": "14:40:12",
            "features": {
                "vehicle_count": 1,
                "person_on_road": True,
                "fire_smoke": False,
                "rollover": False,
                "traffic_impact": "medium",
                "lane_blockage": 1,
                "confidence": 0.89
            },
            "severity_score": 58,
            "severity_label": "Medium",
            "priority_rank": 2,
            "status": "active",
            "severity_factors": {
                "base_score": 35,
                "factors": ["Person on road / shoulder safety hazard (+25 pts)"],
                "factor_breakdown": {"base_stalled": 35, "person_on_road": 25}
            },
            "why_priority_explanation": "Freight truck disabled on breakdown shoulder with driver standing on road.",
            "evidence": {
                "clip_path": "evidence/CAM03_012/clip.mp4",
                "key_frames": ["https://images.unsplash.com/photo-1563720223185-11003d516935?q=80&w=800&auto=format&fit=crop"]
            },
            "timeline": [
                {"time": "14:40:12", "event": "DETECTION_RECEIVED: Disabled freight truck detected in breakdown lane.", "event_type": "DETECTION_RECEIVED"},
                {"time": "14:40:30", "event": "OBSERVATION_UPDATED: Driver standing on road deploying warning triangle.", "event_type": "OBSERVATION_UPDATED"}
            ],
            "report": """INCIDENT ID: CAM03_012
INCIDENT TYPE: STALLED VEHICLE
LOCATION: ORR KM 45, Exit 6 (Lat: 17.456, Lon: 78.372)
TIMESTAMP: 14:40:12 IST
CURRENT STATUS: MONITORING

STRUCTURED OBSERVATIONS:
- Commercial truck disabled on breakdown shoulder.
- Driver positioned behind safety barrier.
- Moderate congestion on exit slip road.

SEVERITY ASSESSMENT:
- Score: 58/100 (Medium Severity)

RECOMMENDED RESPONSE:
- Highway Patrol Assistance.""",
            "response_workflow": "police"
        }
    ]

    for inc in baseline_incidents:
        upsert_incident(inc)

    # Baseline Dispatches
    baseline_dispatches = [
        {
            "dispatch_id": "DISP-CAM02-01",
            "incident_id": "CAM02_004",
            "unit_type": "AMBULANCE",
            "unit_id": "MED-02",
            "station": "Care Hospital Trauma Center",
            "distance_km": 4.1,
            "eta_minutes": 5.1,
            "status": "EN_ROUTE",
            "history": [
                {"time": "14:36:05", "status": "ALERT_SENT"},
                {"time": "14:36:20", "status": "ACKNOWLEDGED"},
                {"time": "14:36:45", "status": "EN_ROUTE"}
            ]
        },
        {
            "dispatch_id": "DISP-CAM02-02",
            "incident_id": "CAM02_004",
            "unit_type": "TOW_RECOVERY",
            "unit_id": "TOW-05",
            "station": "Expressway Recovery Hub",
            "distance_km": 5.8,
            "eta_minutes": 7.0,
            "status": "ACKNOWLEDGED",
            "history": [
                {"time": "14:36:05", "status": "ALERT_SENT"},
                {"time": "14:36:30", "status": "ACKNOWLEDGED"}
            ]
        }
    ]

    for disp in baseline_dispatches:
        upsert_dispatch(disp)

    # Baseline Delivery Logs
    baseline_logs = [
        {
            "log_id": "LOG-001",
            "dispatch_id": "DISP-CAM02-01",
            "recipient_type": "HOSPITAL_EMS",
            "unit_type": "AMBULANCE",
            "message_summary": "SIMULATED DISPATCH: Overturned SUV on Inner Ring Rd. Paramedic unit requested.",
            "delivery_status": "SIMULATED ALERT DELIVERED",
            "timestamp": "14:36:05"
        },
        {
            "log_id": "LOG-002",
            "dispatch_id": "DISP-CAM02-02",
            "recipient_type": "TOWING_GRID",
            "unit_type": "TOW_RECOVERY",
            "message_summary": "SIMULATED DISPATCH: Heavy crane tow needed for lane clearance.",
            "delivery_status": "SIMULATED ALERT DELIVERED",
            "timestamp": "14:36:05"
        }
    ]

    for log in baseline_logs:
        add_delivery_log(log)

    # Baseline SafeWatch Event
    baseline_safewatch = [
        {
            "event_id": "SAFE-06_001",
            "event_type": "POTENTIAL_SAFETY_ANOMALY",
            "camera_id": "CAM-06",
            "location": {"name": "Gachibowli Underpass South", "lat": 17.442, "lon": 78.348},
            "timestamp": "14:45:00",
            "confidence": 0.88,
            "observed_signals": [
                "Unusual prolonged clustering in isolated low-visibility underpass zone",
                "Rapid convergence pattern detected near pedestrian walkway",
                "Context: Off-peak low-pedestrian sector (14:45 IST)"
            ],
            "risk_level": "HIGH",
            "human_review_required": True,
            "status": "PENDING_REVIEW",
            "recommended_response": "AUTHORIZED PATROL / WOMEN'S SAFETY RESPONSE ADVISORY",
            "approved_by": None,
            "approval_timestamp": None,
            "simulated_alert_sent": False,
            "timeline": [
                {"time": "14:45:00", "event": "DETECTION_RECEIVED: Motion tracking identified unusual crowding in low-visibility walkway.", "event_type": "DETECTION_RECEIVED"},
                {"time": "14:45:15", "event": "POTENTIAL_SAFETY_ANOMALY: Classified potential vulnerable-person safety anomaly. Non-identifying spatial tracking.", "event_type": "OBSERVATION_UPDATED"},
                {"time": "14:45:20", "event": "HUMAN_REVIEW_REQUIRED: Operator review card generated in SafeWatch Console.", "event_type": "HUMAN_REVIEW_REQUIRED"}
            ]
        }
    ]

    for sw in baseline_safewatch:
        upsert_safewatch_event(sw)
