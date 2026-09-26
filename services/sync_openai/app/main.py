"""OpenAI text gateway through AWS Bedrock, with bounded concurrency and SDK retries.
USE_BEDROCK=0 keeps deterministic templates. AWS credentials come from the standard SDK chain.
The separate Twilio Realtime audio bridge is not served by this text gateway.
"""
import asyncio
import json
import os
from contextlib import closing
from functools import lru_cache

import boto3
from botocore.config import Config
from fastapi import FastAPI
from pydantic import BaseModel

from services.shared import config

app = FastAPI(title="Project Uzima OpenAI gateway")
MAX_CONCURRENT = int(os.getenv("OPENAI_MAX_CONCURRENT", "5"))
_slots = asyncio.Semaphore(MAX_CONCURRENT)
OPENING = "Hi, this is an AI assistant from Project Uzima, calling for a referring doctor at South Sunflower County Hospital. This call is recorded."


class CompleteRequest(BaseModel):
    messages: list[dict]
    model: str | None = None
    json_mode: bool = False


class PersonaRequest(BaseModel):
    hospital: str
    question: str
    answer: dict


@lru_cache(maxsize=4)
def _bedrock_client(region: str):
    # Boto3 handles profiles, temporary session credentials, roles and SigV4 signing.
    return boto3.Session().client("bedrock-runtime", region_name=region, config=Config(
        connect_timeout=5, read_timeout=30, retries={"mode": "standard", "total_max_attempts": 4}))


def _answer_text(content: str) -> str:
    # Bedrock InvokeModel may prepend GPT OSS reasoning; expose only the final answer.
    if not isinstance(content, str):
        raise ValueError("Bedrock returned no text answer")
    text = content.strip()
    if text.startswith("<reasoning>"):
        _, separator, text = text.partition("</reasoning>")
        if not separator:
            raise ValueError("Bedrock returned an unfinished reasoning block")
        text = text.strip()
    if not text:
        raise ValueError("Bedrock returned an empty answer")
    return text


def _complete_bedrock(req: CompleteRequest) -> str:
    model = req.model or config.env("BEDROCK_MODEL_ID") or "openai.gpt-oss-20b-1:0"
    body = {"model": model, "messages": req.messages, "max_completion_tokens": 2048}
    if req.json_mode:
        body["response_format"] = {"type": "json_object"}
    region = config.env("AWS_REGION") or config.env("AWS_DEFAULT_REGION") or "us-west-2"
    response = _bedrock_client(region).invoke_model(
        modelId=model, body=json.dumps(body), contentType="application/json", accept="application/json")
    with closing(response["body"]) as stream:
        result = json.loads(stream.read())
    return _answer_text(result["choices"][0]["message"]["content"])


async def complete(req: CompleteRequest) -> str:
    async with _slots:
        return await asyncio.to_thread(_complete_bedrock, req)


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
    if not config.has_bedrock():
        return {"mode": "mock", "content": ""}
    return {"mode": "live", "content": await complete(req)}


@app.post("/personas")
async def personas(p: PersonaRequest):
    if not config.has_bedrock():
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
    return {"ok": True, "mode": "live" if config.has_bedrock() else "mock", "max_concurrent": MAX_CONCURRENT}
