"""Smoke test against running services (make dev): start a transfer, wait for answers, accept, print the twin link.

    python3 scripts/smoke.py              # heart attack
    python3 scripts/smoke.py stroke_thrombectomy
"""
import sys
import time

import httpx

O = "http://localhost:8000"
spec = sys.argv[1] if len(sys.argv) > 1 else "cardiac_icu"
case = {"age": 62, "sex": "Male", "specialty": spec, "condition": "demo case", "onset_or_last_known_well": "2026-09-26T14:05:00-05:00"}
print("health:", httpx.get(f"{O}/health").json()["integrations"])
r = httpx.post(f"{O}/transfers", json=case).json()
tid = r["transfer_id"]
print(f"transfer {tid}: calling {len(r['agents'])} centers")
while True:
    s = httpx.get(f"{O}/transfers/{tid}").json()
    print(f"  {s['elapsed_s']:>5}s  answered {s['answered']}/{s['agents']}", end="\r")
    if s["done"]:
        break
    time.sleep(1)
print()
for x in s["results"]:
    print(f"  {x['agent_id']:>3} {x['hospital'][:40]:<40} {x['status']:<19} {x.get('decline_reason') or x.get('ready_in_min') or ''}")
if not s["recommendation"]:
    sys.exit("no yes this round (try again, or set SIM_A1_ANSWER=available)")
a = httpx.post(f"{O}/transfers/{tid}/accept", json={"accepting_physician": "Dr. Demo"}, timeout=60).json()
print(f"accepted: {a['accepted']} · treatment in ~{a['treatment_start_min']} min")
print(f"twin: {a['twin']['shlink'][:80]}…  passcode {a['twin']['passcode']}")
