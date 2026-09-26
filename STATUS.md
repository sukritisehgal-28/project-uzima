# STATUS.md: live board

Pull before reading. Update only your own rows. Times are PT. Statuses: todo, doing, blocked, done, cut.

## Tasks

| # | Task | Lane | Owner (name + tool) | Status | Updated | Result / next step |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | One real live call end to end: phone rings, read-back, events on the map | Voice | Voice teammate | todo | 13:21 | Udit clarified his friend owns calling. Confirmation fix 0e94809 is available; teammate to report real-call outcome |
| 2 | Three live phones at once on the Twilio trial | Voice | Voice teammate | todo | 13:21 | Voice teammate to verify after one-phone test; coordinate with Udit for integrated run |
| 3 | Connect doctors on the live call (summary, then clinician dialed in) | Voice | Voice teammate | todo | 13:21 | Offline summary/dial and rejected-update fallback tests pass; voice teammate owns live verification |
| 4 | Full run with 3 live + 7 simulated, ranking and accept | Core | Udit | todo | 12:30 | `make dev`, default window, heart attack |
| 5 | AWS road times (USE_AWS=1, us-west-2) | Core | Udit + Codex | blocked | 13:21 | Scope: Location project-uzima-routes and DynamoDB project-uzima. CLI installed, but AWS credentials not visible; waiting for hackathon credential file/profile |
| 6 | Dashboard polish to match the deck | Screen | Sukriti + Claude Code | done | 13:35 | White version of the deck's style (Geist, gold accent, light map) for hospital screens; "Ticket created" panel; LIVE tag only when Twilio is live; call-backs counted apart from pending |
| 7 | Demo video of a clean run (about 2 min) | Screen | Sukriti | todo | 12:30 | Record by 2:15 |
| 8 | README screenshots and submission text | Screen | Sukriti | todo | 12:30 | Submit by 2:45 |
| 9 | AgentCore sandboxes | Core | - | cut | 12:30 | Only if 1 to 4 are done by 1:30 |
| 10 | Chaos "kill a sandbox" button | Core | - | cut | 12:30 | Only if 1 to 4 are done by 1:30 |
| 11 | Patient handoff: encrypted record + transfer ticket (web + Apple Wallet) | Screen | Sukriti + Claude Code | done | 13:35 | Ticket at /tickets/{id} (its QR opens the record), viewer at /view, EMTALA handoff content with fictional demo data. Wallet needs the APPLE_* certificate; phones need an https tunnel to 8004 and HANDOFF_PUBLIC_URL |
| 12 | OpenAI text generation through AWS Bedrock | Core / Voice integration | Udit + Codex | blocked | 13:34 | Bedrock text gateway implemented; 49 offline tests pass. Live verification needs AWS credentials; voice adaptation remains with the voice teammate |

## Checkpoints

- 1:00 one live call works
- 1:45 three live phones + Connect
- 2:15 code freeze
- 2:45 submitted

## Messages

Newest at the bottom. One line each: time, who, message.

- 12:30 Udit: Board created. Claim a row before you start.
- 13:35 Sukriti + Claude Code: Pushed the patient handoff (now Sukriti's lane, see docs/PLAN.md) and the white dashboard. Other-lane touches: one line in orchestrator accept() passes `ticket` into the twin; optional handoff fields on `Case` in schemas.py (additive, existing callers unchanged). 23 offline tests pass.
- 13:35 Sukriti: The ticket's QR code is scanned by the receiving team on arrival. Hospitals still only get a phone call to answer, and the ticket is optional. This bends the "no QR for hospitals" rule, so say if you want it hidden in the demo. Dashboard, ticket and record are white on purpose (hospital screens); the deck stays dark.
- 13:35 Sukriti to Voice lane: please have the agent ask the accepting doctor's name on the winning call so the record and ticket show it; today it's a placeholder.
- 13:35 Sukriti to Udit: fixed your two dashboard notes. A1 is no longer tagged LIVE and the screen no longer says doctors were connected when Twilio is in mock mode; call-backs no longer count as pending.

- 12:53 Udit + Codex: Voice lane: adding offline regressions in tests/test_bridge.py for mandatory read-back confirmation and Connect fallback; no shared schema or endpoint changes.

- 13:52 Udit + Codex: Rebasing onto the latest main. Resolving the overlap between Sakshi's URL-based TwiML fix and our earlier rejected-update fallback; preserving both behaviors and both test sets.
- 12:59 Udit + Codex: Browser rehearsal completed in mock mode: all 10 hospitals emitted all four events; Connect created the encrypted handoff and one mock bridge with a passcode summary. Dashboard build and 31 offline tests pass. No real calls placed.
- 12:59 Udit + Codex to Screen lane: Existing mock UI labels A1 live and says doctors connected/record sent; callback_requested stays counted as pending after collector has all 10 results. Observed in transfer 9b271415fe; dashboard left unchanged.
- 13:21 Udit + Codex: Ownership corrected per Udit: his friend handles calling; Udit owns core integration, presenting and AWS. Voice rows are pending teammate verification, not blocked by Udit lacking voice credentials. AWS stays disabled until access and resources are verified.
- 13:22 Udit + Codex: AWS CLI 2.37.4 verified. STS checks for default, clinsight and clinsight-new all return NoCredentials, including a fresh interactive login shell. Installed boto3 locally; no AWS resources created or integration enabled. Need hackathon credentials saved in .env or an authenticated profile.
- 13:26 Udit + Codex: Udit requires OpenAI through AWS Bedrock. Updating the text gateway in services/sync_openai, shared config, dependency/env setup and AWS docs; no endpoint shape changes. Voice teammate must adapt the existing direct Realtime bridge separately; do not claim it runs through Bedrock.
- 13:30 Udit + Codex: Updating AGENTS.md and the README integration row to reflect Udit's Bedrock requirement. Text generation uses the AWS credential chain; direct Realtime voice remains a documented migration dependency owned by the voice teammate.
- 13:34 Udit + Codex: Text gateway now invokes OpenAI GPT OSS through Bedrock with AWS authentication, bounded concurrency and retries, JSON support and template fallback. No direct OpenAI text requests remain. 49 offline tests pass; STS still reports Unable to locate credentials, so USE_BEDROCK and USE_AWS remain disabled and no live AWS result is claimed. Setup and a live verification request are in infra/aws/README.md.
