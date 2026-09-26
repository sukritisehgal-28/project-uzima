"""Patient handoff twin (FR-15..17).

An IPS-shaped FHIR document bundle (HL7 International Patient Summary: medications, allergies, problem list
+ a custom Transfer section with every call, the plan and the ground-vs-air rationale), plus a FHIR Coverage
resource from a real-time eligibility check (X12 270/271 via Stedi; the demo uses Stedi's free mock requests).

Delivered as a SMART Health Link (HL7 IG): the bundle is encrypted as a JWE with alg "dir" / enc "A256GCM",
the link carries the manifest URL (>=256 bits of entropy) and the 32-byte key, flag "P" requires a passcode
that is given to the accepting physician on the physician-to-physician call, and "exp" makes it stale after
24 hours. Any SMART Health Links viewer can open it. Nothing is stored in the clear.
"""
import base64
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from services.shared.schemas import AgentResult, Case, InsuranceCheck, TransportEstimate

app = FastAPI(title="Marco Polo handoff twin")
STEDI = "https://healthcare.us.stedi.com/2024-04-01/change/medicalnetwork/eligibility/v3"
BASE = os.getenv("HANDOFF_URL", "http://localhost:8004")
VIEWER = os.getenv("SHL_VIEWER_URL", "https://shl-viewer.example/")   # any SMART Health Links viewer
_store: dict[str, dict] = {}   # twin_id -> {jwe, passcode, exp}; DynamoDB in production


def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def check_insurance(payer_id: str, member_id: str, first: str, last: str, dob: str) -> InsuranceCheck:
    """Stedi eligibility. With a TEST key only the documented mock member IDs work (free, no real payer)."""
    r = httpx.post(STEDI, headers={"Authorization": os.environ["STEDI_TEST_API_KEY"]},
                   json={"tradingPartnerServiceId": payer_id,
                         "provider": {"organizationName": "South Sunflower County Hospital", "npi": os.getenv("DEMO_NPI", "1999999984")},
                         "subscriber": {"memberId": member_id, "firstName": first, "lastName": last, "dateOfBirth": dob}}, timeout=30)
    r.raise_for_status()
    data = r.json()
    plan = (data.get("planInformation") or {}).get("planNumber") or (data.get("planStatus") or [{}])[0].get("planDetails")
    return InsuranceCheck(payer=payer_id, member_id_masked=f"***{member_id[-4:]}", active=True, plan=plan,
                          checked_at=datetime.now(timezone.utc))


def ips_bundle(case: Case, accepted_hospital_id: str, accepting_physician: str, transport: TransportEstimate,
               calls: list[AgentResult], insurance: Optional[InsuranceCheck]) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    pid = "patient-1"
    entries: list[dict] = []
    entries.append({"resource": {"resourceType": "Patient", "id": pid, "gender": case.sex.lower(),
                                 "extension": [{"url": "http://marco-polo.local/age-years", "valueInteger": case.age}]}})
    entries.append({"resource": {"resourceType": "Condition", "id": "cond-1", "subject": {"reference": f"Patient/{pid}"},
                                 "code": {"text": case.condition}, "onsetDateTime": case.onset_or_last_known_well}})
    for i, (k, v) in enumerate(case.key_scores.items(), start=1):
        entries.append({"resource": {"resourceType": "Observation", "id": f"obs-{i}", "status": "final",
                                     "subject": {"reference": f"Patient/{pid}"}, "code": {"text": k}, "valueQuantity": {"value": v}}})
    med_refs = []
    if case.blood_thinners:
        entries.append({"resource": {"resourceType": "MedicationStatement", "id": "med-1", "status": "active",
                                     "subject": {"reference": f"Patient/{pid}"}, "medicationCodeableConcept": {"text": case.blood_thinners}}})
        med_refs.append({"reference": "MedicationStatement/med-1"})
    if case.imaging_or_ecg:
        entries.append({"resource": {"resourceType": "DiagnosticReport", "id": "dx-1", "status": "final",
                                     "subject": {"reference": f"Patient/{pid}"}, "code": {"text": "ECG / imaging"}, "conclusion": case.imaging_or_ecg}})
    if insurance:
        entries.append({"resource": {"resourceType": "Coverage", "id": "cov-1", "status": "active" if insurance.active else "cancelled",
                                     "beneficiary": {"reference": f"Patient/{pid}"}, "payor": [{"display": insurance.payer}],
                                     "subscriberId": insurance.member_id_masked,
                                     "class": [{"type": {"text": "plan"}, "value": insurance.plan or "unknown"}]}})
    transfer = {"accepted_hospital_id": accepted_hospital_id, "accepting_physician": accepting_physician,
                "transport": transport.model_dump(), "rationale": (
                    f"{transport.recommended_mode} recommended: ground {transport.est_ground_min} min, "
                    f"air {transport.est_air_min} min, tier {transport.tier}"),
                "calls": [c.model_dump(mode="json") for c in calls]}
    composition = {"resourceType": "Composition", "id": "comp-1", "status": "final",
                   "type": {"coding": [{"system": "http://loinc.org", "code": "60591-5", "display": "Patient summary Document"}]},
                   "subject": {"reference": f"Patient/{pid}"}, "date": now, "title": "Marco Polo handoff twin",
                   "author": [{"display": case.sending_physician}],
                   "section": [
                       {"title": "Medication Summary", **({"entry": med_refs} if med_refs else {"emptyReason": {"text": "none reported at transfer"}})},
                       {"title": "Allergies and Intolerances", "emptyReason": {"text": "unknown at transfer"}},
                       {"title": "Problem List", "entry": [{"reference": "Condition/cond-1"}]},
                       {"title": "Transfer", "text": {"status": "generated", "div": "<div xmlns=\"http://www.w3.org/1999/xhtml\">" + json.dumps(transfer) + "</div>"}},
                   ]}
    entries.insert(0, {"resource": composition})
    return {"resourceType": "Bundle", "type": "document", "timestamp": now, "entry": entries}


def make_shl(bundle: dict, passcode: str, hours: int = 24) -> tuple[str, str]:
    """Encrypt the bundle as a JWE (dir / A256GCM) and build the SMART Health Link."""
    key, iv = secrets.token_bytes(32), secrets.token_bytes(12)
    header = b64url(json.dumps({"alg": "dir", "enc": "A256GCM", "cty": "application/fhir+json"}).encode())
    ct = AESGCM(key).encrypt(iv, json.dumps(bundle).encode(), header.encode())
    jwe = f"{header}..{b64url(iv)}.{b64url(ct[:-16])}.{b64url(ct[-16:])}"
    twin_id = secrets.token_urlsafe(32)                       # >= 256 bits of entropy in the manifest URL
    exp = int((datetime.now(timezone.utc) + timedelta(hours=hours)).timestamp())
    _store[twin_id] = {"jwe": jwe, "passcode": passcode, "exp": exp}
    payload = {"url": f"{BASE}/manifests/{twin_id}", "key": b64url(key), "exp": exp, "flag": "P",
               "label": "Marco Polo handoff twin", "v": 1}
    return twin_id, f"{VIEWER}#shlink:/{b64url(json.dumps(payload).encode())}"


def decrypt_shl(jwe: str, key_b64url: str) -> dict:
    """Used by tests and the dashboard preview; a real viewer does the same per the SHL spec."""
    header, _, iv, ct, tag = jwe.split(".")
    pad = lambda s: s + "=" * (-len(s) % 4)
    key = base64.urlsafe_b64decode(pad(key_b64url))
    data = AESGCM(key).decrypt(base64.urlsafe_b64decode(pad(iv)), base64.urlsafe_b64decode(pad(ct)) + base64.urlsafe_b64decode(pad(tag)), header.encode())
    return json.loads(data)


class TwinRequest(BaseModel):
    case: Case
    accepted_hospital_id: str
    accepting_physician: str
    transport: TransportEstimate
    calls: list[AgentResult]
    insurance_test: Optional[dict] = None   # {"payer_id","member_id","first","last","dob"} -> Stedi mock member only


class ManifestRequest(BaseModel):
    recipient: str
    passcode: Optional[str] = None


@app.post("/twins")
def build_twin(req: TwinRequest):
    insurance = None
    if req.insurance_test and os.getenv("STEDI_TEST_API_KEY"):
        insurance = check_insurance(**req.insurance_test)
    bundle = ips_bundle(req.case, req.accepted_hospital_id, req.accepting_physician, req.transport, req.calls, insurance)
    passcode = f"{secrets.randbelow(10**6):06d}"          # read to the accepting physician on the bridge call, sent separately
    twin_id, link = make_shl(bundle, passcode)
    # TODO(FR-16): SMS the link via sync_twilio; TODO: persist _store[twin_id] to DynamoDB
    return {"twin_id": twin_id, "shlink": link, "passcode": passcode, "sections": [s["title"] for s in bundle["entry"][0]["resource"]["section"]]}


@app.post("/manifests/{twin_id}")
def manifest(twin_id: str, req: ManifestRequest):
    t = _store.get(twin_id)
    if not t or t["exp"] < datetime.now(timezone.utc).timestamp():
        raise HTTPException(404)
    if req.passcode != t["passcode"]:
        raise HTTPException(401, "passcode")
    return {"files": [{"contentType": "application/fhir+json", "embedded": t["jwe"]}]}


@app.get("/health")
def health():
    return {"ok": True}
