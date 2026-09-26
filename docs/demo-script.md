# Final demo script (about two minutes)

Use fictional patients and consenting teammate phones. One real hospital roleplay call is enough; identify all other answers as simulated. Have a backup recording ready.

| Time | Owner | Action and narration |
| --- | --- | --- |
| 0:00 | Udit | “Finding a capable hospital still takes repeated phone calls. Uzima asks in parallel and confirms each answer.” |
| 0:15 | Udit | Choose Heart attack, leave the default window, press Find a bed. State how many calls in this run are real. |
| 0:25 | Sakshi | Answer the hospital demo phone on speaker. Let the AI introduce itself and ask about the bed and cath lab. Reply “yes”, “ten minutes”, then confirm its read-back. |
| 0:55 | Udit | Show the confirmed result. Explain that ranking combines the ready time and estimated transport time. Select the confirmed live hospital for the live handoff. |
| 1:10 | Udit | Press Connect. The separate accepting doctor answers and hears the summary; then Udit answers the sending-doctor phone. Exchange one sentence in each direction. The hospital desk can remain on the conference. |
| 1:35 | Sukriti | Show the transfer ticket and open the encrypted record on a phone. The ticket link replaces the old passcode step. |
| 1:50 | Udit | “OpenAI runs through AWS Bedrock. Twilio handles speech and telephone calls. The prototype uses local agents and estimated transport times.” |

Before recording: `make preflight`; participants ready; live calling explicitly enabled; tunnel and services running; phones audible. Do not claim a live connection until both parties can hear each other. If live audio is not verified, label the demonstration as simulated.
