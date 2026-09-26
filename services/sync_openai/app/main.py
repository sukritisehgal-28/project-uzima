"""OpenAI synchronizer: a rate limiter, not a strict one-at-a-time queue."""
import asyncio
import os

from fastapi import FastAPI

app = FastAPI(title="Marco Polo OpenAI synchronizer")
MAX_CONCURRENT = int(os.getenv("OPENAI_MAX_CONCURRENT", "5"))
_slots = asyncio.Semaphore(MAX_CONCURRENT)

# TODO: POST /complete -> acquire a slot, call OpenAI, retry with backoff on 429


@app.get("/health")
def health():
    return {"ok": True, "max_concurrent": MAX_CONCURRENT}
