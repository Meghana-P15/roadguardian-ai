import urllib.request
import json

BASE_URL = "http://localhost:8000"

def request_json(path, method="GET", body=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def verify_live():
    print("--- 0. Resetting Baseline State ---")
    request_json("/reset", method="POST")

    print("--- 1. Testing GET /health ---")
    health = request_json("/health")
    assert health["status"] == "online"
    print("[PASS] Health online:", health["service"])

    print("\n--- 2. Testing Baseline GET /incidents ---")
    incidents = request_json("/incidents")
    print(f"[PASS] Retrieved {len(incidents)} active incidents. Top is #{incidents[0]['priority_rank']}: {incidents[0]['incident_id']} ({incidents[0]['severity_score']}/100)")
    assert incidents[0]["incident_id"] == "CAM02_004"
    assert incidents[2]["incident_id"] == "CAM01_001"

    print("\n--- 3. Testing POST /simulation/scenario/collision_escalation ---")
    res = request_json("/simulation/scenario/collision_escalation", method="POST")
    assert res["status"] == "success"
    print("[PASS] Collision scenario triggered successfully.")

    print("\n--- 4. Verifying Global Re-rank (CAM01_001 -> Priority #1) ---")
    incidents_after = request_json("/incidents")
    top = incidents_after[0]
    print(f"[PASS] New Priority #1: {top['incident_id']} - Score: {top['severity_score']} ({top['severity_label']})")
    assert top["incident_id"] == "CAM01_001"
    assert top["priority_rank"] == 1
    assert top["severity_score"] >= 95

    print("\n--- 5. Verifying Dispatches & Acknowledgment ---")
    dispatches = request_json("/dispatches")
    cam1_disps = [d for d in dispatches if d["incident_id"] == "CAM01_001"]
    assert len(cam1_disps) >= 3
    print(f"[PASS] Found {len(cam1_disps)} dispatches for CAM01_001: {[d['unit_type'] for d in cam1_disps]}")

    disp_id = cam1_disps[0]["dispatch_id"]
    ack_res = request_json(f"/dispatches/{disp_id}/acknowledge", method="POST")
    assert ack_res["status"] == "ACKNOWLEDGED"
    print(f"[PASS] Dispatch {disp_id} acknowledged over live HTTP API.")

    print("\n--- 6. Verifying Delivery Logs ---")
    logs = request_json("/delivery-logs")
    assert len(logs) >= 3
    print(f"[PASS] {len(logs)} Simulated alert delivery logs registered in audit trail.")

    print("\n--- 7. Verifying SafeWatch Module ---")
    sw_events = request_json("/safewatch")
    assert len(sw_events) >= 1
    sw_id = sw_events[0]["event_id"]
    print(f"[PASS] Active SafeWatch event: {sw_id} ({sw_events[0]['event_type']}) - Status: {sw_events[0]['status']}")

    # Operator review approval
    rev_res = request_json(f"/safewatch/{sw_id}/review", method="POST", body={"approved": True, "operator_id": "COMMANDER-01"})
    assert rev_res["status"] == "APPROVED"
    assert rev_res["simulated_alert_sent"] is True
    print(f"[PASS] SafeWatch human operator approval successful over live API.")

    print("\n--- 8. Testing POST /reset ---")
    reset_res = request_json("/reset", method="POST")
    assert reset_res["status"] == "ok"
    print("[PASS] Demo baseline successfully restored via /reset.")

    print("\n[SUCCESS] ALL 8 END-TO-END HTTP API TESTS PASSED PERFECTLY!")

if __name__ == "__main__":
    verify_live()
