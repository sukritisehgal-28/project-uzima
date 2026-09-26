"""Results collector: receives the four call events and full results, streams them to the dashboard, writes bed memory."""
import os
from collections import defaultdict

from fastapi import FastAPI, WebSocket

from services.shared.schemas import AgentResult, CallEvent

app = FastAPI(title="Marco Polo collector")
_clients: set[WebSocket] = set()
_memory: dict[str, dict] = {}                 # hospital_id -> last answer (bed memory); DynamoDB in production
_events: dict[str, list] = defaultdict(list)  # hospital_id -> events (EMTALA log)


async def _broadcast(payload: dict) -> None:
    for ws in list(_clients):
        try:
            await ws.send_json(payload)
        except Exception:
            _clients.discard(ws)


@app.post("/events")
async def post_event(ev: CallEvent):
    _events[ev.hospital_id].append(ev.model_dump(mode="json"))
    await _broadcast({"kind": "event", **ev.model_dump(mode="json")})
    return {"ok": True}


@app.post("/results")
async def post_result(result: AgentResult):
    _memory[result.hospital_id] = {"status": result.status.value, "ready_in_min": result.ready_in_min,
                                   "reason": result.decline_reason, "at": result.answered_at.isoformat() if result.answered_at else None}
    # TODO(FR-14): persist to DynamoDB table os.getenv("DYNAMODB_TABLE") with a 30-minute TTL
    await _broadcast({"kind": "result", **result.model_dump(mode="json")})
    return {"ok": True}


@app.get("/memory")
def memory():
    return _memory


@app.get("/log/{hospital_id}")
def log(hospital_id: str):
    return _events.get(hospital_id, [])


@app.websocket("/stream")
async def stream(ws: WebSocket):
    await ws.accept()
    _clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    finally:
        _clients.discard(ws)
