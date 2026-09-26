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
- The encrypted handoff record (IPS bundle as a SMART Health Link) is still built on Connect but not sent to anyone yet. Sukriti owns it; see "Patient handoff record" below.

## Team

| Who | Owns | Code |
| --- | --- | --- |
| Udit | Core and integration: selection, fan-out, ranking, accept flow, collector. Presents and takes the architecture questions. | `services/orchestrator`, `services/collector`, `services/agent`, `infra`, `data` |
| Sakshi | Voice: Twilio account and verified phones, the Media Streams to OpenAI Realtime bridge, the call script, Connect. | `services/sync_twilio`, `services/sync_openai` |
| Sukriti | Patient handoff: the encrypted record as the patient's wallet for the transfer (patient summary, every call, insurance check). Screen and submission: dashboard, demo video, README, Devpost. | `services/handoff`, `apps/dashboard`, `docs/` |

## Patient handoff record (Sukriti)

**Decided: Sukriti builds it as the patient's wallet for the transfer.** It uses the same QR standard (SMART Health Links) as CMS's [Kill the Clipboard](https://www.cms.gov/initiatives/health-technology-ecosystem/overview/health-tech-ecosystem-categories/your-patient-shows-you-qr-code-you-scan-it-thats-it): a patient's app or wallet makes a QR code, and a clinic scans it to get the patient's history, medications, allergies and insurance. eClinicalWorks has supported it in production since [April 9, 2026](https://hitconsultant.net/2026/04/09/eclinicalworks-cms-kill-the-clipboard-qr-code-patient-intake/). Kill the Clipboard covers check-in at a clinic; ours covers the emergency transfer.

- Read the wallet in: if the patient has a Kill the Clipboard QR code, the sending ER scans it, and their medications and allergies fill the record.
- Open it like a wallet pass: the receiving team unlocks the record with the passcode spoken on the call, ideally in a Kill the Clipboard reader they already have (CMS says community-hosted readers exist today). Test this first: those readers expect the US Core format, and our record follows IPS.

What's built (Sukriti):

- On Connect the orchestrator builds the record: an HL7 IPS patient summary (patient, condition and onset, medications, allergies, problem list), a Transfer section (every call with its answer, reason and transcript; ground vs air rationale) and a Coverage resource from the insurance check (Stedi mock), encrypted as a SMART Health Link (AES-256-GCM, passcode, 24 h expiry). The agent reads the passcode on the winning call.
- Transfer ticket: a boarding-pass style ticket (`/tickets/{id}`) with the route, patient, condition, transport, arrival time, team-ready time, insurance and a QR code of the record link. It never shows the passcode. The dashboard shows "Ticket created" with a QR code that opens the ticket on a phone.
- Apple Wallet: `/tickets/{id}.pkpass` builds and signs the pass. Apple only installs passes signed with a Pass Type ID certificate from an Apple Developer account, so it switches on when `APPLE_PASS_TYPE_ID`, `APPLE_TEAM_ID`, `APPLE_PASS_P12` and `APPLE_WWDR_CERT` are set. Until then the web ticket is the ticket.
- Record viewer: `/view` asks for the passcode, fetches the encrypted file and decrypts it in the browser; the key stays in the link. Ten wrong passcodes lock the link (SMART Health Links rule).
- For phones, run an https tunnel to port 8004 and set `HANDOFF_PUBLIC_URL` to it (browsers only decrypt on https or localhost). Records and tickets are kept in memory, so a restart clears them.
- Still open: if a simulated hospital wins, the fallback call doesn't read the summary.

Still to decide, mainly how the link reaches the receiving team (some of these bend the core rule above):

- Text the link to the accepting doctor right after Connect; the passcode is spoken on the call.
- A QR code that travels with the patient; the receiving team scans it on arrival.
- On stage, a judge scans the QR and unlocks the record with the passcode they just heard.
- A public address for the record (for example through the ngrok tunnel on 8002) and a working viewer.
- Richer fictional case data (ECG, medications given, allergies, weight) so the record is worth opening.

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
| 12:30 | Selection and accept on real events | First live call to one phone, events on the map | Build the patient wallet handoff; agree with the team how the link is delivered. Polish map, cards, clocks, Connect | One live call on the map |
| 1:30 | 3 live phones + 7 simulated, full run | Connect on the live call (summary, then clinician dialed in) | Record screen video of a full run | Full run end to end. Feature freeze |
| 2:15 | Fix blockers only | Backup recording of a clean call | Edit 2-min video, README screenshots | Video done |
| 2:45 | Final push | Test once more | Submit | Submitted |

## Fallbacks

- Live bridge not working by 12:30: keep calls simulated (`SIM_A1_ANSWER=available`) and show the recorded call.
- Connect on the live call fails: the fallback path calls the clinician and dials `DEMO_ACCEPTING_DOCTOR_PHONE`.
- Sandboxes: `LAUNCH_MODE=local` runs every agent as its own async task. Kubernetes Jobs (`LAUNCH_MODE=k8s`) or AgentCore only if time allows; say which one ran.
