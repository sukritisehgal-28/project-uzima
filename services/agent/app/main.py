"""Sandbox template: one container = one hospital call, configured only by its AGENT_HEADER."""
import json
import os

from services.shared.schemas import AgentHeader


def load_header() -> AgentHeader:
    return AgentHeader(**json.loads(os.environ["AGENT_HEADER"]))


def main() -> None:
    header = load_header()
    if header.live:
        from services.agent.app import call_live   # Twilio Media Streams + OpenAI Realtime (FR-7); Retell/Vapi fallback
        call_live.run(header)
    else:
        from services.agent.app import call_sim    # responder + two-persona transcript (FR-8)
        call_sim.run(header)


if __name__ == "__main__":
    main()
