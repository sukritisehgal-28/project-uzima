"""Pure logic of the live call bridge: report_capacity args -> answer_recorded data + AgentResult. Offline."""
from datetime import datetime, timedelta, timezone

from services.shared.schemas import AgentHeader, Status, TranscriptLine
from services.sync_twilio.app.main import answer_data, build_instructions, build_result, default_brief

H = AgentHeader(agent_id="A1", hospital_id="greenville", hospital="Delta Regional", phone="+15550100", lat=33.4, lng=-91.0,
                specialty="cardiac_icu", capability_question="Do you have a cardiac ICU bed and a cath lab team available right now?",
                transport={"est_ground_min": 35, "est_air_min": 18, "recommended_mode": "ground", "tier": "within_target"}, live=True)


def test_bed_yes_is_available_with_treatment_start():
    args = {"bed": True, "ready_in_min": 10, "reason": None, "confirmed": True}
    assert answer_data(args) == {"bed": True, "ready_in_min": 10, "reason": None}
    t0 = datetime.now(timezone.utc)
    lines = [TranscriptLine(speaker="hospital", text="Yes, ten minutes.", at=t0 + timedelta(seconds=5)),
             TranscriptLine(speaker="agent", text="Hi, this is an AI assistant.", at=t0)]
    outcome, r = build_result(H, "T1", args, lines, answered_at=t0)
    assert outcome == "available" and r.status == Status.available
    assert r.ready_in_min == 10 and r.decline_reason is None
    assert r.treatment_start_min == max(35, 10) + 10          # ground travel dominates
    assert [l.speaker for l in r.transcript] == ["agent", "hospital"]   # sorted by time
    assert r.transfer_id == "T1" and r.agent_id == "A1" and r.answered_at == t0


def test_ready_longer_than_travel_and_air_mode():
    h = H.model_copy(update={"transport": H.transport.model_copy(update={"recommended_mode": "air"})})
    _, r = build_result(h, "T1", {"bed": True, "ready_in_min": "25", "confirmed": True}, [])
    assert r.treatment_start_min == max(18, 25) + 10


def test_bed_no_is_declined_with_reason():
    args = {"bed": False, "ready_in_min": 5, "reason": "no staffed bed", "confirmed": True}
    assert answer_data(args) == {"bed": False, "ready_in_min": None, "reason": "no staffed bed"}
    outcome, r = build_result(H, "T1", args, [])
    assert outcome == "declined" and r.status == Status.declined
    assert r.decline_reason == "no staffed bed" and r.ready_in_min is None and r.treatment_start_min is None


def test_bed_no_without_reason_is_unclear():
    assert answer_data({"bed": False, "reason": ""})["reason"] == "unclear"


def test_nothing_reported_is_no_answer():
    outcome, r = build_result(H, "T1", None, [])
    assert outcome == "no_answer" and r.status == Status.no_answer and r.treatment_start_min is None


def test_instructions_disclose_ai_and_ask_question():
    text = build_instructions(H, default_brief(H))
    assert "AI assistant" in text and H.capability_question in text and "report_capacity" in text
    assert "Delta Regional" in default_brief(H)
