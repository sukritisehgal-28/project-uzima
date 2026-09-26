# Project Uzima: plan (v3)

The beds exist. We get people to them in time.

Supersedes PRD v2 (kept in `docs/archive/`). Same code base, updated plan.

## What it does

A clinician says what the patient needs and how fast. Uzima calls every capable hospital inside that time window at once, one AI agent per hospital. Each agent asks, reads the answer back, and only counts it once the hospital confirms. Plain rules pick the best confirmed yes. One tap connects doctor to doctor, and the agent reads the summary to the receiving team first.

## The core rule

Hospitals never open anything. No app, page, link, text or QR code. They get a normal phone call and talk. The agent does all the work.

What changed from v2 because of this rule:

- No SMS to hospitals. `/release` only logs; the agent thanks declining hospitals on the call.
- No SMS link to the accepting doctor. On Connect, the agent reads the summary and the record passcode on the live call, then Twilio dials the referring clinician into that same call.
- The encrypted handoff record (IPS bundle as a SMART Health Link) is still built and kept, but nobody has to open it for the handoff to work.

## Team

| Who | Owns | Code |
| --- | --- | --- |
| Udit | Core and integration: selection, fan-out, ranking, accept flow, collector. Presents and takes the architecture questions. | `services/orchestrator`, `services/collector`, `services/agent`, `infra`, `data` |
| Sakshi | Voice: Twilio account and verified phones, the Media Streams to OpenAI Realtime bridge, the call script, Connect. | `services/sync_twilio`, `services/sync_openai` |
| Sukriti | Screen and submission: dashboard, demo video, README, Devpost. | `apps/dashboard`, `docs/` |

## What's real in the demo

- Real: the zone from the clinician's time window, one agent per hospital running in parallel, 3 live phone calls to verified phones, read-back and confirm on each call, ranking, Connect doctor to doctor on the winning call, the encrypted record.
- Simulated: the other hospitals' answers (weighted random with real reasons), labeled on the map. Hospital coordinates and capabilities come from `data/hospitals.json` (Mississippi Delta, verified sources). Never dial the real `phone_reference` numbers.

## Limits

- Twilio trial: 5 calls at once, verified numbers only (5), 10 min per call, 75 min total. Plan: 3 live hospitals + 1 clinician leg = 4 of 5.
- Time window slider: 10 to 120 min. Untouched = the case default (heart attack 75 min budget, 120 hard max: 10 hospitals).
- Qualifies if the transport time fits the window. Time to treatment = max(transport, ready-in) + 10 min handoff.

## Contracts (frozen)

`services/shared/schemas.py`: `Case` (now with `window_min`), `AgentHeader`, the four `CallEvent`s, `AgentResult`, `TransferEvent`, `HandoffTwin`.
Endpoints: `POST /transfers`, `GET /transfers/{id}`, `POST /transfers/{id}/accept` (orchestrator) · `POST /events`, `POST /results`, `WS /stream` (collector) · `POST /call`, `WS /media`, `POST /bridge` (Twilio gateway).

## Schedule to the 3:00 PM submission

| Time | Udit | Sakshi | Sukriti | Checkpoint |
| --- | --- | --- | --- | --- |
| 11:45 | Pull this branch, `make install`, `make test`, `make dev` | Twilio keys, verify Sakshi + Sukriti phones, ngrok on 8002 | Dashboard running on the fixture | Everyone runs it locally |
| 12:30 | Selection and accept on real events | First live call to one phone, events on the map | Polish map, cards, clocks, Connect | One live call on the map |
| 1:30 | 3 live phones + 7 simulated, full run | Connect on the live call (summary, then clinician dialed in) | Record screen video of a full run | Full run end to end. Feature freeze |
| 2:15 | Fix blockers only | Backup recording of a clean call | Edit 2-min video, README screenshots | Video done |
| 2:45 | Final push | Test once more | Submit | Submitted |

## Fallbacks

- Live bridge not working by 12:30: keep calls simulated (`SIM_A1_ANSWER=available`) and show the recorded call.
- Connect on the live call fails: the fallback path calls the clinician and dials `DEMO_ACCEPTING_DOCTOR_PHONE`.
- Sandboxes: `LAUNCH_MODE=local` runs every agent as its own async task. Kubernetes Jobs (`LAUNCH_MODE=k8s`) or AgentCore only if time allows; say which one ran.
