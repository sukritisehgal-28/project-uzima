"""Pure logic of the live call bridge: report_capacity args -> answer_recorded data + AgentResult. Offline."""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import httpx
import pytest

from fastapi.testclient import TestClient

from services.shared.schemas import AgentHeader, Status, TranscriptLine
from services.sync_twilio.app.main import _twiml_url, answer_data, app, build_instructions, build_result, default_brief
from services.sync_twilio.app import main as gateway

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


def test_twiml_served_by_url_for_get_and_post(monkeypatch):
    monkeypatch.setenv("PUBLIC_HOST", "abcd.ngrok-free.app")
    twiml = '<Response><Say>Hi &amp; bye</Say><Dial>+15550100</Dial></Response>'
    url = _twiml_url(twiml)
    assert url.startswith("https://abcd.ngrok-free.app/twiml/")
    path = url.removeprefix("https://abcd.ngrok-free.app")
    tc = TestClient(app)
    for r in (tc.post(path), tc.get(path)):
        assert r.status_code == 200 and r.text == twiml
        assert r.headers["content-type"].startswith("text/xml")
    assert tc.post("/twiml/nope").status_code == 404


@pytest.mark.parametrize("bed", [True, False])
@pytest.mark.parametrize("confirmed", [False, None, "false", "true", 1])
def test_every_report_requires_boolean_confirmation(bed, confirmed):
    async def run():
        b = gateway.Bridge(AsyncMock(), H, "T1", default_brief(H), "stream", "call")
        b.oai = AsyncMock()
        args = {"bed": bed, "ready_in_min": 10 if bed else None, "reason": None, "confirmed": confirmed}
        for _ in range(2):  # A repeated unconfirmed call must never bypass the guard.
            await b._on_tool({"name": "report_capacity", "call_id": "tool", "arguments": json.dumps(args)})
            assert b.report is None and b._emit_q.empty()
            outputs = [json.loads(c.args[0]) for c in b.oai.send.call_args_list
                       if json.loads(c.args[0])["type"] == "conversation.item.create"]
            assert json.loads(outputs[-1]["item"]["output"])["ok"] is False
        # A subsequent confirmed answer may be recorded, exactly once.
        args["confirmed"] = True
        try:
            await b._on_tool({"name": "report_capacity", "call_id": "tool", "arguments": json.dumps(args)})
            await b._on_tool({"name": "report_capacity", "call_id": "duplicate", "arguments": json.dumps(args)})
            assert b.report == args
            path, event = b._emit_q.get_nowait()
            assert path == "/events" and event["type"] == "answer_recorded"
            assert event["data"]["bed"] is bed
            assert b._emit_q.empty()
        finally:
            for task in b._tasks:
                task.cancel()
            await asyncio.gather(*b._tasks, return_exceptions=True)
    asyncio.run(run())


@pytest.mark.parametrize("arguments", ["not json", "[]", "null"])
def test_malformed_report_does_not_record_an_answer(arguments):
    async def run():
        b = gateway.Bridge(AsyncMock(), H, "T1", default_brief(H), "stream", "call")
        b.oai = AsyncMock()
        await b._on_tool({"name": "report_capacity", "call_id": "tool", "arguments": arguments})
        assert b.report is None and b._emit_q.empty()
    asyncio.run(run())


def test_connect_updates_winning_call_with_summary_before_dial(monkeypatch):
    monkeypatch.setattr(gateway.config, "has_twilio", lambda: True)
    monkeypatch.setattr(gateway, "live_calls", {("T1", "A1"): {"call_sid": "winning-call"}})
    send = AsyncMock(return_value={"sid": "winning-call"})
    monkeypatch.setattr(gateway, "_twilio", send)
    req = gateway.BridgeRequest(transfer_id="T1", agent_id="A1", summary="Summary & passcode 1234",
                                clinician="+15550101", fallback_hospital="+15550102")
    result = asyncio.run(gateway.bridge(req))
    assert result["via"] == "live_call" and send.await_count == 1
    path, data = send.call_args.args
    assert path == "Calls/winning-call.json"
    assert "Twiml" not in data
    twiml = gateway.twiml_docs[data["Url"].rsplit("/", 1)[-1]]
    assert twiml == '<Response><Say>Summary &amp; passcode 1234</Say><Dial>+15550101</Dial></Response>'


def test_connect_rejected_update_uses_configured_fallback(monkeypatch):
    monkeypatch.setattr(gateway.config, "has_twilio", lambda: True)
    monkeypatch.setattr(gateway, "live_calls", {("T1", "A1"): {"call_sid": "ended-call"}})
    response = httpx.Response(400, request=httpx.Request("POST", "https://api.twilio.com/test"))
    error = httpx.HTTPStatusError("Call no longer active", request=response.request, response=response)
    send = AsyncMock(side_effect=[error, {"sid": "fallback-call"}])
    monkeypatch.setattr(gateway, "_twilio", send)
    req = gateway.BridgeRequest(transfer_id="T1", agent_id="A1", clinician="+15550101", fallback_hospital="+15550102")
    result = asyncio.run(gateway.bridge(req))
    assert result == {"mode": "live", "sid": "fallback-call", "via": "new_call"}
    assert send.await_count == 2
    path, data = send.call_args.args
    assert path == "Calls.json" and data["To"] == req.clinician
    assert "Twiml" not in data
    assert "<Dial>+15550102</Dial>" in gateway.twiml_docs[data["Url"].rsplit("/", 1)[-1]]


def test_connect_rejected_update_without_fallback_does_not_redial(monkeypatch):
    monkeypatch.setattr(gateway.config, "has_twilio", lambda: True)
    monkeypatch.setattr(gateway, "live_calls", {("T1", "A1"): {"call_sid": "ended-call"}})
    response = httpx.Response(400, request=httpx.Request("POST", "https://api.twilio.com/test"))
    send = AsyncMock(side_effect=httpx.HTTPStatusError("Call no longer active", request=response.request, response=response))
    monkeypatch.setattr(gateway, "_twilio", send)
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(gateway.bridge(gateway.BridgeRequest(transfer_id="T1", agent_id="A1", clinician="+15550101")))
    assert send.await_count == 1
