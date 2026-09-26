import base64
import json
from datetime import datetime, timezone

from services.handoff.app.main import _store, decrypt_shl, ips_bundle, make_shl
from services.shared.schemas import AgentResult, Case, InsuranceCheck, Specialty, Status, TransportEstimate


def test_ips_bundle_as_smart_health_link_roundtrip():
    case = Case(age=62, sex="Male", specialty=Specialty.cardiac_icu, condition="STEMI", onset_or_last_known_well="2026-09-26T14:05:00-05:00",
                key_scores={"HEART": 7}, imaging_or_ecg="ST elevation V1-V4", blood_thinners="apixaban")
    t = TransportEstimate(est_ground_min=42, est_air_min=45, recommended_mode="ground", tier="within_target")
    calls = [AgentResult(agent_id="A1", hospital_id="delta_health", hospital="Delta Health", lat=0, lng=0, status=Status.available,
                         ready_in_min=10, transport=t, treatment_start_min=52)]
    ins = InsuranceCheck(payer="mock", member_id_masked="***1", active=True, checked_at=datetime.now(timezone.utc))
    twin_id, link = make_shl(ips_bundle(case, "delta_health", "Dr. A", t, calls, ins), "123456")
    payload = json.loads(base64.urlsafe_b64decode(link.split("#shlink:/")[1] + "=="))
    assert payload["flag"] == "P" and len(twin_id) >= 43
    out = decrypt_shl(_store[twin_id]["jwe"], payload["key"])
    assert [s["title"] for s in out["entry"][0]["resource"]["section"]] == ["Medication Summary", "Allergies and Intolerances", "Problem List", "Transfer"]
    assert "Coverage" in {e["resource"]["resourceType"] for e in out["entry"]}
