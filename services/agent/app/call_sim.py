"""Simulated call: emits the four events, generates a short two-persona transcript, posts the result."""
import random
import time
from datetime import datetime, timezone

from services.agent.app.events import emit, emit_result
from services.agent.app.responder import respond
from services.shared.schemas import AgentHeader, AgentResult, Status, TranscriptLine

LARGE = {"ummc", "baptist_memphis", "methodist_university", "uams", "baptist_little_rock", "regional_one", "nmmc_tupelo"}


def run(header: AgentHeader) -> None:
    now = lambda: datetime.now(timezone.utc)
    emit("call_started", header.agent_id, header.hospital_id)
    time.sleep(random.uniform(3, 12))  # stagger so the map fills in over 20-60 s
    answer = respond(header.specialty.value, header.hospital_id in LARGE)
    lines = [TranscriptLine(speaker="agent", at=now(), text=(
        "Hi, this is an AI transfer assistant calling for South Sunflower County Hospital. This call is recorded. "
        f"{header.capability_question}"))]
    if answer["status"] == "no_answer":
        emit("call_ended", header.agent_id, header.hospital_id, outcome="no_answer")
        status, ready, reason = Status.no_answer, None, None
    else:
        emit("call_answered", header.agent_id, header.hospital_id)
        if answer["status"] == "available":
            lines.append(TranscriptLine(speaker="hospital", at=now(), text="Yes, we can take the patient."))
            lines.append(TranscriptLine(speaker="agent", at=now(), text="When can you be ready to receive?"))
            lines.append(TranscriptLine(speaker="hospital", at=now(), text=f"About {answer['ready_in_min']} minutes."))
            status, ready, reason = Status.available, answer["ready_in_min"], None
        elif answer["status"] == "callback_requested":
            lines.append(TranscriptLine(speaker="hospital", at=now(), text="Call us back in five minutes, checking with the charge nurse."))
            status, ready, reason = Status.callback_requested, None, None
        else:
            lines.append(TranscriptLine(speaker="hospital", at=now(), text=f"No, sorry - {answer['decline_reason']}."))
            status, ready, reason = Status.declined, None, answer["decline_reason"]
        emit("answer_recorded", header.agent_id, header.hospital_id, bed=(status == Status.available), ready_in_min=ready, reason=reason)
        emit("call_ended", header.agent_id, header.hospital_id, outcome=status.value)
    # TODO: replace the fixed lines with two OpenAI personas via sync_openai for more natural transcripts
    t = header.transport
    start = None if ready is None else max(t.est_ground_min if t.recommended_mode == "ground" else t.est_air_min, ready) + 10
    emit_result(AgentResult(agent_id=header.agent_id, hospital_id=header.hospital_id, hospital=header.hospital, lat=header.lat, lng=header.lng,
                            status=status, ready_in_min=ready, decline_reason=reason, transport=t, treatment_start_min=start,
                            transcript=lines, answered_at=now()))
