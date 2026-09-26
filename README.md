# Project Uzima

**The beds exist. We get people to them in time.**

Uzima helps a referring clinician find a receiving hospital. Parallel agents ask about the required capability and bed, collect a ready time, read the answer back, and wait for explicit confirmation. The dashboard ranks confirmed answers by estimated time to treatment. Connect reads the referral summary to the receiving doctor, then dials the referring clinician. The transfer ticket links to an encrypted patient handoff record.

This is a hackathon prototype using fictional patients and teammate phones. Receiving hospitals only need to answer a phone. The ticket is an optional record for the receiving team.

## Current integration

- **OpenAI through AWS Bedrock:** GPT OSS 20B in `us-west-2`; text generation and interpretation of spoken hospital responses.
- **Voice:** Twilio speech recognition and speech synthesis, with a staged availability → ready time → read-back → confirmation flow. Default `VOICE_PROVIDER=bedrock_gather`; no direct OpenAI key required. A legacy Realtime implementation remains available only through explicit configuration.
- **Core:** local asynchronous agents, confirmed-result ranking, collector and live dashboard.
- **Handoff:** encrypted FHIR-shaped record, transfer ticket and browser viewer, 24-hour expiry. No record passcode; possession of the link grants access. Records and tickets currently live in memory.
- **Data:** 18 receiving centers; transport times are estimates. Hospital capability sources are in `data/hospitals.json`.
- **Not active:** DynamoDB, AWS Location, EKS, AgentCore, Apple Wallet signing and live insurance verification. Current workshop permissions deny the DynamoDB and Location checks. Insurance is explicitly mocked.

See [the final integration plan](docs/INTEGRATION_PLAN.md), [demo script](docs/demo-script.md), and [team board](STATUS.md). The older [project plan](docs/PLAN.md) describes the broader design; this README and the final integration plan describe the release.

## Run

```bash
make install
cp .env.example .env     # only on a fresh checkout; preserve an existing .env
make test
make dev
```

Open `http://localhost:5173`. All services run locally. `.env` is private and excluded from Git.

```bash
make preflight          # actual Bedrock + HTTPS checks; never dials
make smoke              # simulated rehearsal; refuses to dial live phones
```

For an offline rehearsal, use `TWILIO_ENABLED=0`, `SIM_A1_ANSWER=available`. Leave `USE_BEDROCK=1` to exercise AWS text generation, or use `0` for deterministic template transcripts. Restart `make dev` after environment changes.

## Live phone setup

1. Set valid AWS credentials, `USE_BEDROCK=1`, `AWS_REGION=us-west-2`, `BEDROCK_MODEL_ID=openai.gpt-oss-20b-1:0`.
2. Set Twilio account SID, auth token and voice number. Add only consenting teammate numbers to `DEMO_HOSPITAL_PHONES`, `DEMO_SENDING_DOCTOR_PHONE` and `DEMO_ACCEPTING_DOCTOR_PHONE`.
3. Start an HTTPS tunnel to the restricted public gateway on port 8005. One option is `cloudflared tunnel --url http://localhost:8005 --no-autoupdate`. Its temporary URL changes if the tunnel is recreated.
4. Set `PUBLIC_HOST` to its hostname without a scheme, `HANDOFF_PUBLIC_URL` to the HTTPS URL and `SHL_VIEWER_URL` to that URL plus `/view`.
5. Set `VOICE_PROVIDER=bedrock_gather` and `TWILIO_ENABLED=1`. Restart services and refresh the dashboard.
6. Run `make preflight`. With both participants ready, press Find a bed. A scripted live rehearsal is also available with `.venv/bin/python scripts/smoke.py --live`.

**A passing preflight does not prove phone audio works.** Complete the two-person rehearsal in the integration plan. The dashboard reports a connection request, never claims two-way audio is verified automatically.

## Services

| Service | Port | Purpose |
| --- | --- | --- |
| Orchestrator | 8000 | Selection, fan-out, ranking, Connect and handoff |
| Bedrock text | 8001 | Model inference using AWS authentication |
| Voice | 8002 | Twilio dial/control and signed speech callbacks |
| Collector | 8003 | Call results, events and dashboard WebSocket |
| Handoff | 8004 | Encrypted records, transfer tickets, viewer |
| Public gateway | 8005 | Only voice callbacks, TwiML documents and handoff links |
| Dashboard | 5173 | Clinician map and transfer controls |

The public gateway excludes call creation, doctor connection, transfer creation and internal result endpoints. Speech callbacks require a valid Twilio signature. Keep the Twilio service to one worker because active calls are stored in memory.

## Reliability and validation

- A failed live call yields a live error/no-answer result, never synthetic availability.
- Voice answers are read back and require an unqualified confirmation. Corrections restart fact collection. Duplicate callbacks do not create another result.
- Connect checks both handoff and phone-service responses. A failed request remains retryable; concurrent/repeated successful requests return the existing result.
- Both the existing-call and fallback-call paths read the summary to the receiving doctor before dialing the referring clinician.
- Search timeout accommodates the live-call timeout. Results identify whether they are live or simulated.
- Tests cover the offline end-to-end transfer, encrypted record, voice state machine, correction/confirmation, callback signatures, bridge failure/retry and public endpoint restrictions.

## Demo limits

This runs on one laptop with a temporary HTTPS tunnel; it is not a cloud deployment. Memory resets when services restart. Travel estimates and timing comparisons are demo assumptions. The encrypted handoff format and clinical content have not been certified for clinical use. Never dial real hospital reference numbers in the dataset.

## Team

| Owner | Responsibility |
| --- | --- |
| Udit | Core, AWS integration, final rehearsal and presentation |
| Sakshi | Real phone conversation and doctor connection verification |
| Sukriti | Dashboard, handoff, demo recording and submission |
