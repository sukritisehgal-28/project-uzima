# Project Uzima

**The beds exist. We get people to them in time.**

A clinician says what the patient needs and how fast. Uzima calls every capable hospital inside that time window at the same time, one AI agent per hospital. Each agent reads the answer back and only counts it once the hospital confirms. Plain rules pick the best confirmed yes, and one tap connects doctor to doctor. Hospitals never open anything: they just answer the phone.

- Plan (v3, current): [docs/PLAN.md](docs/PLAN.md)
- Demo script: [docs/demo-script.md](docs/demo-script.md)
- Earlier plan (v2): [docs/archive/](docs/archive/)
- Demo data: South Sunflower County Hospital, Indianola, MS as the sending hospital; 15 verified receiving centers in MS, TN and AR (`data/hospitals.json`).

## Layout

| Path | What it is |
| --- | --- |
| `data/hospitals.json` | Sending hospital, 15 verified centers with graded capability sources, survival windows, transport estimates, demo cases |
| `services/shared/schemas.py` | Case, agent header, the four call events, agent result, handoff twin |
| `services/orchestrator/` | Center selection inside the window, bed-memory skip, swarm launch, ranking, hold and release |
| `services/agent/` | Sandbox template: live call (A1) or simulated responder + transcript; emits the four events |
| `services/sync_openai/` | Rate limiter for model calls |
| `services/sync_twilio/` | Twilio Voice + Media Streams ↔ OpenAI Realtime (`WS /media`), read-back and `report_capacity`, Connect on the live call |
| `services/collector/` | Receives events/results, streams to the dashboard, bed memory, EMTALA log |
| `services/handoff/` | Patient handoff twin: HL7 IPS bundle delivered as a SMART Health Link (JWE A256GCM, 24 h expiry; the ticket's QR code opens it), with a Stedi mock insurance check |
| `apps/dashboard/` | React + Vite + Tailwind + MapLibre live map |
| `infra/` | Kubernetes Job template, App Runner fallback, DynamoDB table |
| `scripts/run_local_swarm.py` | Whole swarm in one process, no network: `python3 scripts/run_local_swarm.py cardiac_icu` |
| `scripts/replay_fixture.py` + `data/fixtures/` | Replay sample events into the collector so the dashboard moves without a live call |
| `docs/` | PRD, pitch deck text, team plan, verified numbers with grades, competitors, demo script |

## Run it

Everything runs locally with **no keys**: every integration has a mock, and adding its key to `.env` switches it on.

```bash
make install          # Python venv + dashboard packages
make test             # 15 tests, including the whole flow end to end in one process
make dev              # all services + dashboard; open http://localhost:5173, set "Care within", press "Find a bed"
make smoke            # (with make dev running) start a transfer, wait for answers, accept, print the twin link
```

| Service | Port | Without keys | Switches to live when `.env` has |
| --- | --- | --- | --- |
| Orchestrator | 8000 | Swarm runs in-process | `LAUNCH_MODE=k8s` (one Job per hospital); `USE_AWS=1` + `AWS_LOCATION_ROUTE_CALCULATOR` for road times |
| OpenAI text gateway via Bedrock | 8001 | Template transcripts | `USE_BEDROCK=1`, AWS credentials, `AWS_REGION`, `BEDROCK_MODEL_ID` (default `openai.gpt-oss-20b-1:0`) |
| Twilio gateway | 8002 | Logs calls/SMS to `/outbox` | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `PUBLIC_HOST` (ngrok), `OPENAI_API_KEY`, `DEMO_HOSPITAL_PHONES`, `DEMO_SENDING_DOCTOR_PHONE` |
| Collector | 8003 | In memory | `USE_AWS=1` + `DYNAMODB_TABLE` |
| Handoff twin + ticket | 8004 | Offline insurance mock; web ticket at `/tickets/{id}`, record viewer at `/view` | `STEDI_TEST_API_KEY` + `STEDI_MOCK_*`; `HANDOFF_PUBLIC_URL` (https tunnel to 8004) for phones; `APPLE_*` for Apple Wallet |
| Dashboard | 5173 | MapLibre demo tiles | `VITE_MAP_STYLE` (AWS Location map style URL) |

`GET localhost:8000/health` shows which integrations are live. `SIM_A1_ANSWER=available` makes the live agents say yes when there is no live call; `SIM_TIME_SCALE=0` makes simulated answers instant.

## Architecture

One agent template runs as N isolated pods on Amazon EKS; only the header (hospital, phone, location, capability question, transport tier) changes per pod. Every call path emits the same four events, so the voice provider can be swapped without touching the dashboard.

```mermaid
flowchart TD
  U[Rural doctor<br/>call, text or click] --> O[Orchestrator<br/>FastAPI + OpenAI]
  O -->|select centers inside<br/>the survival window| K[EKS sandbox template x N<br/>A1 live, A2..An simulated]
  K --> S1[OpenAI synchronizer<br/>rate limiter]
  K --> S2[Twilio synchronizer<br/>Voice + Media Streams -> OpenAI Realtime<br/>own cluster]
  S1 --> R[Collector<br/>4 events + results, WebSocket]
  S2 --> R
  R --> D[Dashboard<br/>React + Vite + Tailwind + MapLibre]
  R --> M[(DynamoDB<br/>bed memory, EMTALA log, twins)]
  M -->|skip centers full < 30 min| O
  O -->|on physician acceptance| H[Handoff twin<br/>AES-256-GCM + Stedi mock eligibility]
  L[AWS Location Service<br/>road routing + map tiles] --> O
  L --> D
```

**One call, four events**

```mermaid
sequenceDiagram
  participant A as Agent An (pod)
  participant H as Hospital line
  participant C as Collector
  A->>C: call_started
  A->>H: "AI transfer assistant… this call is recorded" + one-breath case
  H-->>A: answers
  A->>C: call_answered
  A->>H: Q1 capability + bed? · Q2 ready in how many minutes?
  H-->>A: yes/no (+reason), ready-in
  A->>C: answer_recorded {bed, ready_in_min, reason}
  A->>C: call_ended {outcome} + full AgentResult (transport, time to treatment, transcript)
```

**Selection and ranking**

1. Keep only centers with the needed capability (cardiac ICU + cath lab · thrombectomy · Level I/II trauma, plus burn or pediatric center when needed).
2. Ground if it fits the transport budget; else air if it fits; else the faster mode inside the hard max. Beyond the hard max: not called unless a physician overrides.
3. Skip centers that said "full" in the last 30 minutes (bed memory).
4. Time to treatment = max(transport by recommended mode, ready-in) + 10 min handoff. Lowest wins; hold the best, release the rest on acceptance.

| Case | Transport budget | Hard max |
| --- | --- | --- |
| Heart attack (STEMI) | 75 min | 120 min |
| Stroke, large-vessel | 90 min | 240 min |
| Trauma (adult, burn, pediatric) | 60 min | 90 min |

**Deployment.** EKS for the swarm and services; the Twilio synchronizer in its own cluster; DynamoDB for memory, log and twins; AWS Location for routing and tiles; App Runner (or one EC2 box) and `scripts/run_local_swarm.py` as the no-Kubernetes fallback. Live voice Option A is Twilio Media Streams + OpenAI Realtime; Option B (fallback) is a Retell or Vapi agent on an OpenAI model. The handoff twin is an IPS-shaped FHIR bundle encrypted as a SMART Health Link; the eligibility check (X12 270/271) runs after acceptance and never gates the transfer (EMTALA 42 CFR 489.24(d)(4)).

## Team

| Who | Owns |
| --- | --- |
| Udit | Core and integration: orchestrator, collector, agents, infra, data. Presents. |
| Sakshi | Voice: Twilio gateway, Media Streams to OpenAI Realtime bridge, Connect. |
| Sukriti | Patient handoff: the encrypted record as the patient's wallet for the transfer (`services/handoff`). Screen and submission: dashboard, video, docs. |

## Rules

- Hospitals get a phone call and nothing else: no app, link, text or QR code.
- Live calls go only to verified teammate phones (`DEMO_HOSPITAL_PHONES`). Every other agent runs the same code against a simulated responder.
- Never dial the real hospital numbers in `data/hospitals.json` (`phone_reference` is reference only).
- The agent says it is an AI in its first line, reads every answer back, and a clinician confirms every transfer. Fictional patients only.
