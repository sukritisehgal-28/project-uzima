"""Patient handoff twin: structured record of the transfer, encrypted, with an insurance eligibility check (FR-20/21).

- Built after physician acceptance from the case, every call result and the transport plan.
- Encrypted with AES-256-GCM (key in HANDOFF_ENCRYPTION_KEY); the accepting team gets a one-time link by SMS.
- Insurance: Stedi real-time eligibility (270/271). The demo uses Stedi's free mock requests with a test API key
  and fixed test member IDs, so no real payer or patient data is involved.
"""
import base64
import json
import os
import uuid
from datetime import datetime, timezone

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import FastAPI

from services.shared.schemas import AgentResult, Case, HandoffTwin, InsuranceCheck, TransportEstimate

app = FastAPI(title="Marco Polo handoff twin")
STEDI = "https://healthcare.us.stedi.com/2024-04-01/change/medicalnetwork/eligibility/v3"


def encrypt(twin: HandoffTwin) -> dict:
    key = base64.b64decode(os.environ["HANDOFF_ENCRYPTION_KEY"])  # 32 bytes, base64
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, twin.model_dump_json().encode(), None)
    return {"twin_id": twin.twin_id, "nonce": base64.b64encode(nonce).decode(), "ciphertext": base64.b64encode(ct).decode()}


def check_insurance(payer_id: str, member_id: str, first: str, last: str, dob: str) -> InsuranceCheck:
    """Stedi mock: must use the documented test member IDs with a test API key (free)."""
    r = httpx.post(STEDI, headers={"Authorization": os.environ["STEDI_TEST_API_KEY"]},
                   json={"tradingPartnerServiceId": payer_id, "provider": {"organizationName": "South Sunflower County Hospital", "npi": "[demo npi]"},
                         "subscriber": {"memberId": member_id, "firstName": first, "lastName": last, "dateOfBirth": dob}}, timeout=15)
    r.raise_for_status()
    data = r.json()
    plan = (data.get("planInformation") or {}).get("planNumber")
    return InsuranceCheck(payer=payer_id, member_id_masked=f"***{member_id[-4:]}", active=True, plan=plan, checked_at=datetime.now(timezone.utc))


@app.post("/twins")
def build_twin(case: Case, accepted_hospital_id: str, accepting_physician: str, transport: TransportEstimate, calls: list[AgentResult]):
    twin = HandoffTwin(twin_id=str(uuid.uuid4()), case=case, accepted_hospital_id=accepted_hospital_id, accepting_physician=accepting_physician,
                       transport=transport, calls=calls, insurance=None, created_at=datetime.now(timezone.utc), emtala_log_ref=f"log/{accepted_hospital_id}")
    # TODO: run check_insurance() with a Stedi test member; TODO(FR-12): SMS a one-time link via sync_twilio
    return encrypt(twin)


@app.get("/health")
def health():
    return {"ok": True}
