"""Live call for A1: Twilio Voice + Media Streams bridged to OpenAI Realtime (FR-7).

Option A (primary): our sync_twilio service answers Twilio's media stream WebSocket and pipes audio to/from
OpenAI Realtime; the model asks Q1/Q2 and returns structured answers. Option B (fallback by 12:00 on the day):
a Retell or Vapi agent on an OpenAI model, which sends transcript + answers by webhook. Both emit the same
four events, so the dashboard does not change.
"""
from services.shared.schemas import AgentHeader


def run(header: AgentHeader) -> None:
    raise NotImplementedError("Wire sync_twilio /call (Option A) or the Retell/Vapi webhook (Option B); emit the four events + result")
