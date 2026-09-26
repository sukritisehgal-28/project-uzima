"""Twilio synchronizer: live voice (A1) via Twilio Voice + Media Streams bridged to OpenAI Realtime, SMS, callbacks.

Runs in its own cluster. Needs a public URL for Twilio webhooks (ngrok on a laptop).
Start from Twilio's Media Streams + OpenAI Realtime sample, then add: disclosure line, Q1/Q2, answer extraction,
the four events, and recording (FR-19) as a transcription backup.
"""
from fastapi import FastAPI

app = FastAPI(title="Marco Polo Twilio synchronizer")

# TODO(FR-7): POST /call {agent header} -> dial DEMO_HOSPITAL_PHONE, <Connect><Stream> to /media, bridge to OpenAI Realtime
# TODO(FR-12): POST /sms {to, text}; POST /bridge {sending_doctor, accepting_doctor} -> conference the two physicians
# TODO(FR-19): enable call recording


@app.get("/health")
def health():
    return {"ok": True}
