import base64
import hashlib
import hmac
import re
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from services.sync_twilio.app import main as gateway


def test_accepting_doctor_is_dialed_then_summary_then_sending_doctor(monkeypatch):
    monkeypatch.setattr(gateway.config, "has_twilio", lambda: True)
    monkeypatch.setenv("PUBLIC_HOST", "voice.test")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "secret")
    send = AsyncMock(side_effect=[{"sid": "accepting"}, {"sid": "sending"}, {"sid": "desk"}])
    monkeypatch.setattr(gateway, "_twilio", send)
    monkeypatch.setattr(gateway, "live_calls", {("T3", "A1"): {"call_sid": "desk"}})
    tc = TestClient(gateway.app)
    r = tc.post("/bridge", json={"transfer_id": "T3", "agent_id": "A1", "summary": "Referral & summary",
                "clinician": "+15550000001", "accepting_doctor": "+15550000002"})
    assert r.status_code == 200 and r.json()["via"] == "doctor_conference"
    assert send.await_count == 1
    assert send.call_args.args[1]["To"] == "+15550000002"
    xml = gateway.twiml_docs[send.call_args.args[1]["Url"].rsplit("/", 1)[-1]]
    assert xml.index("Referral &amp; summary") < xml.index("<Redirect")
    token = re.search(r"doctor-ready/([a-f0-9]+)", xml).group(1)
    path = f"/doctor-ready/{token}"
    body = "https://voice.test" + path + "CallSidaccepting"
    signature = base64.b64encode(hmac.new(b"secret", body.encode(), hashlib.sha1).digest()).decode()
    assert tc.post(path, data={"CallSid": "accepting"}).status_code == 403
    response = tc.post(path, data={"CallSid": "accepting"}, headers={"X-Twilio-Signature": signature})
    assert response.status_code == 200 and "<Conference" in response.text
    assert send.await_args_list[1].args[1]["To"] == "+15550000001"
    assert send.await_args_list[2].args[0] == "Calls/desk.json"
    again = tc.post(path, data={"CallSid": "accepting"}, headers={"X-Twilio-Signature": signature})
    assert again.text == response.text and send.await_count == 3
