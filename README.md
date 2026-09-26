# Marco Polo

An AI agent swarm that finds an accepting ICU for a critical patient leaving a rural hospital — heart attack, stroke, or trauma — by calling every capable center inside the patient's survival window at the same time, then letting a physician confirm the best yes. In the game, one player calls "Marco" and everyone answers "Polo" at once.

- PRD v2: https://claude.ai/code/artifact/8e418b30-6d2d-454b-aecc-391a4caf2978
- Demo region: Mississippi Delta — sending hospital South Sunflower County Hospital, Indianola; 15 verified receiving centers in MS, TN and AR.

## Layout

| Path | What it is |
| --- | --- |
| `data/hospitals.json` | Sending hospital, 15 verified centers with graded capability sources, survival windows, transport estimates, demo cases |
| `services/shared/schemas.py` | Case, agent header, the four call events, agent result, handoff twin |
| `services/orchestrator/` | Center selection inside the window, bed-memory skip, swarm launch, ranking, hold and release |
| `services/agent/` | Sandbox template: live call (A1) or simulated responder + transcript; emits the four events |
| `services/sync_openai/` | Rate limiter for model calls |
| `services/sync_twilio/` | Twilio Voice + Media Streams ↔ OpenAI Realtime, SMS, physician bridge (own cluster) |
| `services/collector/` | Receives events/results, streams to the dashboard, bed memory, EMTALA log |
| `services/handoff/` | Encrypted patient handoff twin + Stedi mock insurance check |
| `apps/dashboard/` | React + Vite + Tailwind + MapLibre live map |
| `infra/` | Kubernetes Job template, App Runner fallback, DynamoDB table |
| `scripts/run_local_swarm.py` | Whole swarm in one process, no network: `python3 scripts/run_local_swarm.py cardiac_icu` |
| `docs/` | Verified numbers with sources and grades, competitors, demo script |

## Rules
- A1 is a real call to a teammate's phone. Every other agent runs the same code against a simulated responder.
- Never dial the real hospital numbers in `data/hospitals.json` (`phone_reference` is reference only).
- Fictional patients only; no severity scoring by the AI; a physician accepts every transfer.
