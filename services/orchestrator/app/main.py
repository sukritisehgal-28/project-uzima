"""Orchestrator: case summary, center selection, bed memory, swarm launch, ranking, hold and release."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI

from services.shared.schemas import AgentHeader, Case, Specialty, TransportEstimate

app = FastAPI(title="Marco Polo orchestrator")
DATA = json.loads((Path(__file__).resolve().parents[3] / "data" / "hospitals.json").read_text())
CENTERS = {c["id"]: c for c in DATA["centers"]}
HANDOFF_MIN = 10
SWARM_TIMEOUT = int(os.getenv("SWARM_TIMEOUT_SECONDS", "90"))

QUESTION = {
    Specialty.cardiac_icu: "Do you have a cardiac ICU bed and a cath lab team available right now?",
    Specialty.stroke_thrombectomy: "Do you have a neuro ICU bed and a thrombectomy team available right now?",
    Specialty.trauma_adult: "Do you have a trauma bay and surgical team available right now?",
    Specialty.trauma_burn: "Do you have a burn ICU bed and burn team available right now?",
    Specialty.trauma_pediatric: "Do you have a pediatric trauma bay and team available right now?",
}


def select_centers(specialty: Specialty, memory: dict | None = None) -> list[AgentHeader]:
    """Every capable center inside the survival window, nearest first; skips centers memory says are full."""
    case = DATA["demo_cases"][specialty.value]
    headers = []
    for i, cid in enumerate(case["called_by_default"], start=1):
        if memory and memory.get(cid, {}).get("status") == "declined":
            continue  # FR: bed memory - skip a center that said full in the last 30 min
        c = CENTERS[cid]
        e = case["eligibility"][cid]
        headers.append(AgentHeader(
            agent_id=f"A{i}", hospital_id=cid, hospital=c["name"], phone=os.getenv("DEMO_HOSPITAL_PHONE", "[demo phone]"),
            lat=c["lat"], lng=c["lng"], specialty=specialty, capability_question=QUESTION[specialty],
            transport=TransportEstimate(est_ground_min=c["est_ground_min"], est_air_min=c["est_air_min"],
                                        recommended_mode=e["mode"], tier=e["tier"]),
            live=(i == 1),
        ))
    return headers


def treatment_start(transport: TransportEstimate, ready_in_min: int) -> int:
    t = transport.est_ground_min if transport.recommended_mode == "ground" else transport.est_air_min
    return max(t, ready_in_min) + HANDOFF_MIN


@app.get("/health")
def health():
    return {"ok": True, "centers": len(CENTERS), "swarm_timeout_s": SWARM_TIMEOUT}


@app.post("/transfers")
def start_transfer(case: Case):
    # TODO(FR-1): missing-field check; TODO(FR-5): launch one sandbox per header (K8s Job or fallback runner)
    headers = select_centers(case.specialty)
    return {"started_at": datetime.now(timezone.utc).isoformat(), "agents": [h.model_dump(mode="json") for h in headers]}

# TODO(FR-9): stop when all agents finish or SWARM_TIMEOUT elapses
# TODO(FR-10): rank yeses by treatment_start(); tie -> higher capability level
# TODO(FR-11/12): hold the best, release the rest, SMS summary, physician-to-physician bridge
# TODO(FR-20): build the handoff twin after acceptance (services/handoff)
