"""Twilio gateway: live A1 call, SMS, release messages and the physician bridge. Runs in its own cluster.
Without Twilio keys every endpoint logs what it would do and returns mode "mock"."""
import logging
from html import escape

import httpx
from fastapi import FastAPI, WebSocket
from pydantic import BaseModel

from services.shared import config

app = FastAPI(title="Marco Polo Twilio gateway")
log = logging.getLogger("sync_twilio")
outbox: list[dict] = []   # what was sent (or would have been, in mock mode), for the demo and tests


class CallRequest(BaseModel):
    header: dict
    transfer_id: str


class SmsRequest(BaseModel):
    to: str
    text: str


class ReleaseRequest(BaseModel):
    hospital: str
    phone: str


class BridgeRequest(BaseModel):
    a: str
    b: str


async def _twilio(path: str, data: dict) -> dict:
    sid = config.env("TWILIO_ACCOUNT_SID")
    async with httpx.AsyncClient(timeout=20, auth=(sid, config.env("TWILIO_AUTH_TOKEN"))) as c:
        r = await c.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/{path}", data=data)
        r.raise_for_status()
        return r.json()


def _mock(kind: str, **payload) -> dict:
    outbox.append({"kind": kind, **payload})
    log.info("MOCK %s %s", kind, payload)
    return {"mode": "mock", "kind": kind}


@app.post("/call")
async def call(req: CallRequest):
    if not config.has_twilio():
        return _mock("call", to=req.header.get("phone"), agent=req.header.get("agent_id"))
    public = config.env("PUBLIC_HOST")   # ngrok host, e.g. abcd.ngrok-free.app
    twiml = (f'<Response><Connect><Stream url="wss://{public}/media">'
             f'<Parameter name="transfer_id" value="{escape(req.transfer_id)}"/>'
             f'<Parameter name="agent_id" value="{escape(req.header["agent_id"])}"/></Stream></Connect></Response>')
    r = await _twilio("Calls.json", {"To": req.header["phone"], "From": config.env("TWILIO_FROM_NUMBER"), "Twiml": twiml})
    return {"mode": "live", "sid": r.get("sid")}


@app.websocket("/media")
async def media(ws: WebSocket):
    """TODO(Engine): bridge Twilio's media stream to OpenAI Realtime: disclosure line, Q1 and Q2, extract the
    answers, then POST the four events and the AgentResult to the collector (same shapes as the simulated call)."""
    await ws.accept()
    async for msg in ws.iter_json():
        if msg.get("event") == "stop":
            break


@app.post("/sms")
async def sms(req: SmsRequest):
    if not config.has_twilio():
        return _mock("sms", to=req.to, text=req.text)
    r = await _twilio("Messages.json", {"To": req.to, "From": config.env("TWILIO_FROM_NUMBER"), "Body": req.text})
    return {"mode": "live", "sid": r.get("sid")}


@app.post("/release")
async def release(req: ReleaseRequest):
    text = f"Marco Polo: thank you, {req.hospital}. The patient has been placed elsewhere; please release the bed."
    return await sms(SmsRequest(to=req.phone, text=text))


@app.post("/bridge")
async def bridge(req: BridgeRequest):
    if not config.has_twilio():
        return _mock("bridge", a=req.a, b=req.b)
    twiml = f"<Response><Say>Connecting you to the accepting physician.</Say><Dial>{escape(req.b)}</Dial></Response>"
    r = await _twilio("Calls.json", {"To": req.a, "From": config.env("TWILIO_FROM_NUMBER"), "Twiml": twiml})
    return {"mode": "live", "sid": r.get("sid")}


@app.get("/outbox")
def get_outbox():
    return outbox


@app.get("/health")
def health():
    return {"ok": True, "mode": "live" if config.has_twilio() else "mock"}
