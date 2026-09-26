# STATUS.md: live board

Pull before reading. Update only your own rows. Times are PT. Statuses: todo, doing, blocked, done, cut.

## Tasks

| # | Task | Lane | Owner (name + tool) | Status | Updated | Result / next step |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | One real live call end to end: phone rings, read-back, events on the map | Voice | Udit + Codex | blocked | 12:56 | Local app runs; confirmation bypass fixed; 31 offline tests pass. Real call untested: needs Twilio/OpenAI credentials and ngrok auth (ERR_NGROK_4018). .env stays untracked |
| 2 | Three live phones at once on the Twilio trial | Voice | Udit + Codex | blocked | 12:56 | Await successful one-phone test and three user-verified numbers; no real calls placed |
| 3 | Connect doctors on the live call (summary, then clinician dialed in) | Voice | Udit + Codex | blocked | 12:56 | Offline tests verify summary before dial and fallback after rejected live-call update. Needs live call, clinician phone and fallback phone for real verification |
| 4 | Full run with 3 live + 7 simulated, ranking and accept | Core | Udit | todo | 12:30 | `make dev`, default window, heart attack |
| 5 | AWS road times (USE_AWS=1, us-west-2) | Core | Udit | todo | 12:30 | Optional; skip if access denied |
| 6 | Dashboard polish to match the deck | Screen | Sukriti + Claude Code | done | 13:35 | White version of the deck's style (Geist, gold accent, light map) for hospital screens; "Ticket created" panel; LIVE tag only when Twilio is live; call-backs counted apart from pending |
| 7 | Demo video of a clean run (about 2 min) | Screen | Sukriti | todo | 12:30 | Record by 2:15 |
| 8 | README screenshots and submission text | Screen | Sukriti | todo | 12:30 | Submit by 2:45 |
| 9 | AgentCore sandboxes | Core | - | cut | 12:30 | Only if 1 to 4 are done by 1:30 |
| 10 | Chaos "kill a sandbox" button | Core | - | cut | 12:30 | Only if 1 to 4 are done by 1:30 |
| 11 | Patient handoff: encrypted record + transfer ticket (web + Apple Wallet) | Screen | Sukriti + Claude Code | done | 13:35 | Ticket at /tickets/{id} (its QR opens the record), viewer at /view, EMTALA handoff content with fictional demo data. Wallet needs the APPLE_* certificate; phones need an https tunnel to 8004 and HANDOFF_PUBLIC_URL |

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
