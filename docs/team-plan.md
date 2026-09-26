# Team plan: three people, three lanes, one merge

Each lane owns its own directories and talks to the others only through frozen contracts, so the three branches merge without conflicts. Every lane has a working demo on its own by 12:00 (with fixtures or stubs) and the three join at the checkpoints.

## Lanes

| Lane | Owner | Main role | Owns (nobody else edits) | Done on the day when |
| --- | --- | --- | --- | --- |
| **Engine** | Person 1 | The live call and the agents | `services/agent/`, `services/sync_twilio/`, `services/sync_openai/` | A teammate's phone rings, the AI discloses itself, asks Q1 and Q2, and the four events land in the collector; A2–An resolve with realistic answers and transcripts |
| **Backbone** | Person 2 | Orchestration, data, cloud, handoff twin | `services/orchestrator/`, `services/collector/`, `services/handoff/`, `infra/`, `data/` | Selection inside the survival window, ranking, hold and release, DynamoDB memory + log, AWS Location road times, EKS (or App Runner) launch, SMART Health Link twin with the Stedi mock check |
| **Face** | Person 3 | Dashboard, pitch, demo | `apps/dashboard/`, `docs/deck.md`, backup video, rehearsal | Map, cards, two clocks, recommendation card, twin panel with QR; deck with measured time; three clean rehearsals; plays the accepting physician on the bridge call |

## Contracts (frozen at 10:30; changes only by a PR all three approve)

| Contract | Producer → consumer | Where |
| --- | --- | --- |
| `AgentHeader`, `CallEvent`, `AgentResult`, `TwinRequest` | shared | `services/shared/schemas.py` |
| `POST /events`, `POST /results`, `WS /stream`, `GET /memory`, `GET /log/{hospital_id}` | Engine → Backbone → Face | `services/collector` |
| `POST /transfers {Case}` → agent headers | Face → Backbone | `services/orchestrator` |
| `POST /call {AgentHeader}`, `POST /sms {to,text}`, `POST /bridge {a,b}` | Backbone → Engine | `services/sync_twilio` |
| `POST /twins {TwinRequest}` → `{shlink, passcode}`; `POST /manifests/{id}` | Face → Backbone | `services/handoff` |
| `data/hospitals.json` (centers, windows, demo cases) | Backbone → all | `data/` |
| `data/fixtures/events_sample.json` (replayable events + results) | Backbone → Face | `data/fixtures/` |

## Working without each other

- Face builds the dashboard against `data/fixtures/events_sample.json` replayed into the collector (`python3 scripts/replay_fixture.py`), so no live call is needed to see the map move.
- Engine tests against a local collector (`uvicorn services.collector.app.main:app --port 8003`) and the fallback runner; the live call only needs Twilio + OpenAI keys and ngrok.
- Backbone tests selection and ranking with `scripts/run_local_swarm.py` (no network) and the twin with the local handoff test.

## Branches and merging

- Branches: `engine`, `backbone`, `face`. Small commits, PR into `main`, one reviewer from another lane. `main` stays runnable at all times.
- Touch only your lane's directories. A change to `services/shared/schemas.py` or a collector endpoint is a contract change: PR, all three approve, everyone rebases.
- Rebase on `main` at every checkpoint. Conflicts are almost impossible by construction; if one appears, the lane owner of that file resolves it.

## Checkpoints

| Time | What must be true on `main` |
| --- | --- |
| 10:30 | Contracts frozen; everyone has keys; fixture replays on the dashboard |
| 12:00 | Engine: one real call end to end, events visible on Face's dashboard. Not clean → switch to Retell/Vapi (Option B) |
| 13:00 | Backbone: DynamoDB writes, bed memory, road times from AWS Location |
| 14:30 | Full swarm run: A1 live + simulated agents, ranking, hold and release, twin panel shows the SMART Health Link |
| 15:30 | Code freeze; only fixes. Face records the backup video and fills the measured time into the deck |
| 16:15–17:00 | Three rehearsals under 3 minutes; Engine plays the A1 hospital, Face pitches, Backbone drives the dashboard |

## Tonight (Friday)

| Lane | Tasks |
| --- | --- |
| Engine | Twilio account + number; verify all three phones; OpenAI key with Realtime; Retell or Vapi agent; ngrok; clone Twilio's Media Streams + OpenAI Realtime sample and get one test call |
| Backbone | AWS account: DynamoDB table, Location route calculator + map, EKS or App Runner; Stedi test key and one mock 271; `HANDOFF_ENCRYPTION_KEY`; run `run_local_swarm.py` for both cases |
| Face | `npm install`, map tiles rendering with Indianola centered, fixture replay working; read `docs/deck.md`; draft the 3-minute pitch |
| All | Register for the AWS Builder Loft (separate from Luma); physical photo ID; plan the route to 525 Market St |
