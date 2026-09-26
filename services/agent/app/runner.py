"""One agent = one hospital call. Live for A1 when Twilio keys exist; otherwise the simulated call (same events)."""
import logging

from services.agent.app.call_sim import run_sim
from services.agent.app.events import Emitter
from services.shared import config
from services.shared.schemas import AgentHeader, AgentResult

log = logging.getLogger("agent")


async def run_agent(header: AgentHeader, transfer_id: str) -> AgentResult:
    emit = Emitter(header, transfer_id)
    if header.live and config.has_twilio():
        try:
            from services.agent.app.call_live import run_live
            return await run_live(header, emit)
        except Exception as e:
            log.warning("live call failed, simulating A1: %s", e)
    return await run_sim(header, emit)
