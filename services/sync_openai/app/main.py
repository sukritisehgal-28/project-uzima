"""OpenAI gateway: a rate limiter (several requests at once, retry with backoff) plus persona transcripts.
Without OPENAI_API_KEY it returns deterministic template text, so everything still runs."""
import asyncio
import json
import os

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from services.shared import config

app = FastAPI(title="Project Uzima OpenAI gateway")
MAX_CONCURRENT = int(os.getenv("OPENAI_MAX_CONCURRENT", "5"))
_slots = asyncio.Semaphore(MAX_CONCURRENT)
OPENING = "Hi, this is an AI transfer assistant calling for South Sunflower County Hospital. This call is recorded."


class CompleteRequest(BaseModel):
    messages: list[dict]
    model: str | None = None
    json_mode: bool = False


class PersonaRequest(BaseModel):
    hospital: str
    question: str
    answer: dict


async def complete(req: CompleteRequest) -> str:
    async with _slots:
        body = {"model": req.model or config.env("OPENAI_MODEL", "gpt-4o-mini"), "messages": req.messages}
        if req.json_mode:
            body["response_format"] = {"type": "json_object"}
        delay = 1.0
        for attempt in range(4):
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post("https://api.openai.com/v1/chat/completions", json=body,
                                 headers={"Authorization": f"Bearer {config.env('OPENAI_API_KEY')}"})
            if r.status_code in (429, 500, 502, 503) and attempt < 3:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    raise RuntimeError("unreachable")


def template_lines(p: PersonaRequest) -> list[dict]:
    lines = [{"speaker": "agent", "text": f"{OPENING} {p.question}"}]
    a = p.answer
    if a.get("status") == "available":
        lines += [{"speaker": "hospital", "text": "Yes, we can take the patient."},
                  {"speaker": "agent", "text": "When can you be ready to receive?"},
                  {"speaker": "hospital", "text": f"About {a.get('ready_in_min')} minutes."}]
    elif a.get("status") == "callback_requested":
        lines += [{"speaker": "hospital", "text": "Call us back in five minutes, checking with the charge nurse."}]
    else:
        lines += [{"speaker": "hospital", "text": f"No, sorry - {a.get('decline_reason', 'no bed')}."}]
    return lines


@app.post("/complete")
async def post_complete(req: CompleteRequest):
    if not config.has_openai():
        return {"mode": "mock", "content": ""}
    return {"mode": "live", "content": await complete(req)}


@app.post("/personas")
async def personas(p: PersonaRequest):
    if not config.has_openai():
        return {"mode": "mock", "lines": template_lines(p)}
    prompt = ("Write a realistic, very short phone exchange (3-5 lines) between an AI transfer assistant and the "
              f"transfer line at {p.hospital}. The assistant opens with: \"{OPENING}\" and asks: \"{p.question}\" "
              f"The hospital's answer must match exactly: {json.dumps(p.answer)}. If available, the assistant also asks "
              "when they can be ready. Return JSON {\"lines\":[{\"speaker\":\"agent\"|\"hospital\",\"text\":...}]}.")
    try:
        content = await complete(CompleteRequest(messages=[{"role": "user", "content": prompt}], json_mode=True))
        return {"mode": "live", "lines": json.loads(content)["lines"]}
    except Exception:
        return {"mode": "fallback", "lines": template_lines(p)}


@app.get("/health")
def health():
    return {"ok": True, "mode": "live" if config.has_openai() else "mock", "max_concurrent": MAX_CONCURRENT}
