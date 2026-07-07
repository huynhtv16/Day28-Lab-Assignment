# api-gateway/main.py
from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field
import httpx
import os
import time


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    embedding: list[float] = Field(default_factory=lambda: [0.0] * 384)

app = FastAPI(title="AI Platform API Gateway")
Instrumentator().instrument(app).expose(app)  # Integration 9: Prometheus

VLLM_URL = os.environ.get("VLLM_URL", "").rstrip("/")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")

@app.post("/api/v1/chat")
async def chat(body: ChatRequest):
    start = time.time()
    context = []

    # 1. Vector search. If Qdrant is not ready yet, keep the gateway usable.
    async with httpx.AsyncClient() as client:
        try:
            search_resp = await client.post(
                f"{QDRANT_URL}/collections/documents/points/search",
                json={"vector": body.embedding, "limit": 3},
                timeout=5,
            )
            if search_resp.status_code == 200:
                context = search_resp.json().get("result", [])
        except httpx.HTTPError:
            context = []

    # 2. LLM inference
    prompt = f"Context: {context}\n\nQuery: {body.query}"
    latency = (time.time() - start) * 1000
    fallback_answer = (
        "Platform engineering is the practice of building paved paths, shared "
        "infrastructure, automation, and observability so product teams can ship "
        "software and AI workloads reliably."
    )

    if not VLLM_URL:
        return {
            "answer": fallback_answer,
            "latency_ms": round(latency, 2),
            "model": "local-fallback",
            "degraded": True,
        }

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            llm_resp = await client.post(
                f"{VLLM_URL}/v1/chat/completions",
                json={
                    "model": "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4",
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            llm_resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail=f"LLM service unavailable: {exc}") from exc

    latency = (time.time() - start) * 1000
    result = llm_resp.json()

    return {
        "answer": result["choices"][0]["message"]["content"],
        "latency_ms": round(latency, 2),
        "model": result["model"]
    }

@app.get("/health")
def health():
    return {"status": "ok"}
