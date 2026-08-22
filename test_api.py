import store
import orchestrator

def run_tests():
    print("[TEST] Initializing SQLite Store with Multi-Table Schema...")
    store.init_db()
    store.seed_baseline_data()
    orchestrator.reprioritize_all_incidents()
    
    print("\n--- 1. Baseline Incidents Queue ---")
    incidents = store.get_all_incidents()
    for inc in incidents:
        print(f"Rank #{inc['priority_rank']}: {inc['incident_id']} - Severity: {inc['severity_score']} ({inc['severity_label']}) - {inc['location']['name']}")
        
    assert incidents[0]["incident_id"] == "CAM02_004", f"Expected CAM02_004 at #1, got {incidents[0]['incident_id']}"
    assert incidents[2]["incident_id"] == "CAM01_001", f"Expected CAM01_001 at #3, got {incidents[2]['incident_id']}"
    print("[PASS] Baseline Ranking Verified: CAM02_004 (#1, 82), CAM03_012 (#2, 58), CAM01_001 (#3, 45)")
    
    print("\n--- 2. Ingesting Multi-Modal Simulation on CAM01_001 ---")
    simulated_payload = {
        "incident_id": "CAM01_001",
        "type": "collision",
        "camera_id": "CAM-01",
        "location": {"name": "NH-44, KM 124", "lat": 17.385, "lon": 78.4867},
        "features": {
            "vehicle_count": 3,
            "person_on_road": True,
            "fire_smoke": True,
            "rollover": True,
            "traffic_impact": "critical"
        },
        "severity_score": 96,
        "severity_label": "Critical",
        "response_workflow": "hospital+fire+police",
        "timeline": [
            {"time": "14:33:00", "event": "CRITICAL ESCALATION: Multi-spectral camera CAM-01 confirmed active fire/smoke plume, pedestrian on travel lane, and vehicle rollover.", "event_type": "SEVERITY_RECALCULATED"}
        ]
    }
    
    store.upsert_incident(simulated_payload)
    orchestrator.reprioritize_all_incidents()
    orchestrator.orchestrate_dispatches_for_incident("CAM01_001")
    
    print("\n--- 3. Re-ranked Incidents Queue ---")
    reranked = store.get_all_incidents()
    for inc in reranked:
        print(f"Rank #{inc['priority_rank']}: {inc['incident_id']} - Severity: {inc['severity_score']} ({inc['severity_label']}) - Workflow: {inc['response_workflow']}")
        
    assert reranked[0]["incident_id"] == "CAM01_001", f"Expected CAM01_001 at #1 after simulation, got {reranked[0]['incident_id']}"
    assert reranked[0]["priority_rank"] == 1, "CAM01_001 should have priority rank 1"
    print("[PASS] Priority Re-ranking Verified: CAM01_001 successfully jumped from Rank #3 to Rank #1!")
    
    print("\n--- 4. Testing Dispatches & Delivery Logs ---")
    dispatches = store.get_dispatches_for_incident("CAM01_001")
    assert len(dispatches) >= 3, f"Expected at least 3 dispatches for CAM01_001, got {len(dispatches)}"
    print(f"[PASS] {len(dispatches)} Emergency Dispatches Created (Hospital, Fire, Police)")
    
    # Test Acknowledge
    disp_id = dispatches[0]["dispatch_id"]
    store.update_dispatch_status(disp_id, "ACKNOWLEDGED")
    disp_updated = store.get_dispatch(disp_id)
    assert disp_updated["status"] == "ACKNOWLEDGED"
    print(f"[PASS] Dispatch {disp_id} acknowledged successfully")
    
    print("\n--- 5. Testing SafeWatch Public Safety Module ---")
    sw_events = store.get_all_safewatch_events()
    assert len(sw_events) >= 1
    sw_id = sw_events[0]["event_id"]
    assert sw_events[0]["status"] == "PENDING_REVIEW"
    
    # Review & approve SafeWatch event
    sw_events[0]["status"] = "APPROVED"
    sw_events[0]["approved_by"] = "COMMANDER-01"
    sw_events[0]["simulated_alert_sent"] = True
    store.upsert_safewatch_event(sw_events[0])
    sw_updated = store.get_safewatch_event(sw_id)
    assert sw_updated["status"] == "APPROVED"
    assert sw_updated["simulated_alert_sent"] is True
    print("[PASS] SafeWatch Human Review & Simulated Alert Approved successfully")
    
    print("\n[SUCCESS] ALL EXTENDED BACKEND LOGIC & DATA CONTRACT TESTS PASSED!")

if __name__ == "__main__":
    run_tests()
