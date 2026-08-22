from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class LocationModel(BaseModel):
    name: str
    lat: float
    lon: float

class FeaturesModel(BaseModel):
    vehicle_count: int = 1
    person_on_road: bool = False
    fire_smoke: bool = False
    rollover: bool = False
    traffic_impact: str = "low"  # low, medium, high, critical
    lane_blockage: Optional[int] = 1
    confidence: Optional[float] = 0.92

class EvidenceModel(BaseModel):
    clip_path: str = ""
    key_frames: List[str] = []

class TimelineItem(BaseModel):
    time: str
    event: str
    event_type: Optional[str] = "DETECTION_RECEIVED"

class SeverityFactorsModel(BaseModel):
    base_score: int
    factors: List[str]
    factor_breakdown: Dict[str, int]

class DispatchRecord(BaseModel):
    dispatch_id: str
    incident_id: str
    unit_type: str  # AMBULANCE, FIRE_RESCUE, HIGHWAY_PATROL, TRAFFIC_POLICE, TOW_RECOVERY
    unit_id: str
    station: str
    distance_km: float
    eta_minutes: float
    status: str  # ALERT_SENT, ACKNOWLEDGED, EN_ROUTE, ARRIVED, STANDBY
    created_at: str
    updated_at: str
    history: List[Dict[str, str]] = []

class DeliveryLog(BaseModel):
    log_id: str
    dispatch_id: str
    recipient_type: str  # HOSPITAL_EMS, FIRE_CONTROL, POLICE_DISPATCH, TOWING_GRID, SHE_TEAM
    unit_type: str
    message_summary: str
    delivery_status: str  # SIMULATED ALERT DELIVERED
    timestamp: str

class SafeWatchEvent(BaseModel):
    event_id: str
    event_type: str  # POTENTIAL_SAFETY_ANOMALY, VULNERABLE_PERSON_ASSISTANCE, RESTRICTED_AREA_ANOMALY
    camera_id: str
    location: LocationModel
    timestamp: str
    confidence: float
    observed_signals: List[str]
    risk_level: str  # ELEVATED, HIGH, CRITICAL
    human_review_required: bool = True
    status: str  # PENDING_REVIEW, APPROVED, REJECTED, DISPATCHED
    recommended_response: str
    approved_by: Optional[str] = None
    approval_timestamp: Optional[str] = None
    simulated_alert_sent: bool = False
    timeline: List[TimelineItem] = []

class IncidentInput(BaseModel):
    incident_id: str
    type: str = "collision"
    camera_id: str = "CAM-01"
    location: LocationModel
    timestamp: Optional[str] = None
    features: Optional[FeaturesModel] = None
    severity_score: Optional[int] = None
    severity_label: Optional[str] = None
    evidence: Optional[EvidenceModel] = None
    timeline: Optional[List[TimelineItem]] = None
    report: Optional[str] = None
    response_workflow: Optional[str] = None
    status: Optional[str] = "active"

class IncidentSummaryOutput(BaseModel):
    incident_id: str
    type: str
    camera_id: str
    location: LocationModel
    priority_rank: int
    status: str
    severity_label: str
    severity_score: int
    why_priority_explanation: Optional[str] = None

class IncidentDetailOutput(IncidentSummaryOutput):
    timestamp: str
    features: FeaturesModel
    evidence: EvidenceModel
    timeline: List[TimelineItem]
    report: str
    response_workflow: str
    severity_factors: Optional[SeverityFactorsModel] = None
    dispatches: Optional[List[DispatchRecord]] = []
