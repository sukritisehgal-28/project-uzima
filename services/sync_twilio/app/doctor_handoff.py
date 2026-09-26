"""Ring the accepting doctor, read the summary, then join the sending doctor."""
import asyncio
from html import escape
from urllib.parse import parse_qs
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException, Request, Response

from services.shared import config
from services.sync_twilio.app.gather import validate_signature

router = APIRouter()
handoffs: dict[str, dict] = {}


def conference(room: str) -> str:
    return f'<Dial><Conference beep="false" endConferenceOnExit="true">{escape(room)}</Conference></Dial>'


async def start(req, hospital_entry: dict | None) -> dict:
    from services.sync_twilio.app.main import _twilio, _twiml_url
    token = uuid4().hex
    room = "uzima-" + token
    state = {"room": room, "req": req, "hospital": hospital_entry, "lock": asyncio.Lock(), "reply": None}
    handoffs[token] = state
    ready_url = f"https://{config.env('PUBLIC_HOST')}/doctor-ready/{token}"
    # The redirect happens only after the accepting doctor hears the summary.
    twiml = (f'<Response><Say>{escape(req.summary or "This is the Uzima AI assistant with a demo referral.")}</Say>'
             f'<Redirect method="POST">{escape(ready_url)}</Redirect></Response>')
    result = await _twilio("Calls.json", {"To": req.accepting_doctor, "From": config.env("TWILIO_FROM_NUMBER"),
                                        "Url": _twiml_url(twiml), "Timeout": "30", "TimeLimit": "300"})
    state["accepting_sid"] = result.get("sid")
    return {"mode": "live", "sid": result.get("sid"), "via": "doctor_conference", "status": "calling_accepting_doctor"}


@router.post("/doctor-ready/{token}")
async def ready(token: str, request: Request):
    from services.sync_twilio.app.main import _twilio, _twiml_url
    params = parse_qs((await request.body()).decode(), keep_blank_values=True)
    validate_signature(request, params)
    state = handoffs.get(token)
    if not state:
        raise HTTPException(404)
    async with state["lock"]:
        if state["reply"] is not None:
            return Response(state["reply"], media_type="text/xml")
        join = conference(state["room"])
        req = state["req"]
        try:
            sending = await _twilio("Calls.json", {"To": req.clinician or req.a,
                "From": config.env("TWILIO_FROM_NUMBER"), "Timeout": "30", "TimeLimit": "300",
                "Url": _twiml_url('<Response><Say>The accepting doctor is joining your referral handoff.</Say>' + join + '</Response>')})
            state["sending_sid"] = sending.get("sid")
            # Include the hospital desk if its original call is still open. A
            # closed reception call must not prevent the two doctors joining.
            entry = state["hospital"] or {}
            if entry.get("call_sid"):
                try:
                    await _twilio(f'Calls/{entry["call_sid"]}.json', {"Url": _twiml_url(
                        '<Response><Say>The accepting and referring doctors are joining the handoff.</Say>' + join + '</Response>')})
                except httpx.HTTPError:
                    pass
            state["reply"] = '<Response><Say>Connecting you to the referring doctor now.</Say>' + join + '</Response>'
        except httpx.HTTPError:
            # Cache the response so a repeated provider callback cannot redial.
            state["reply"] = '<Response><Say>We could not reach the referring doctor. Please contact them directly.</Say><Hangup/></Response>'
        return Response(state["reply"], media_type="text/xml")
