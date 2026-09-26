"""Emit the four call events (+ the final result) to the collector."""
import os
from datetime import datetime, timezone

import httpx

from services.shared.schemas import AgentResult, CallEvent

COLLECTOR = os.getenv("COLLECTOR_URL", "http://localhost:8003")


def emit(event_type: str, agent_id: str, hospital_id: str, **data) -> None:
    ev = CallEvent(type=event_type, agent_id=agent_id, hospital_id=hospital_id, at=datetime.now(timezone.utc), data=data)
    httpx.post(f"{COLLECTOR}/events", json=ev.model_dump(mode="json"), timeout=5)


def emit_result(result: AgentResult) -> None:
    httpx.post(f"{COLLECTOR}/results", json=result.model_dump(mode="json"), timeout=5)
