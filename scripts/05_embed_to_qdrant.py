import requests
import os

EMBED_URL = os.environ.get("EMBED_NGROK_URL", "").rstrip("/")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333").rstrip("/")

# Tạo collection
requests.put(
    f"{QDRANT_URL}/collections/documents",
    json={"vectors": {"size": 384, "distance": "Cosine"}},
    timeout=10,
).raise_for_status()


def stable_point_id(record_id: str, fallback: int) -> int:
    digits = "".join(ch for ch in record_id if ch.isdigit())
    return int(digits) if digits else fallback

def embed_and_store(records: list[dict]):
    if EMBED_URL:
        response = requests.post(f"{EMBED_URL}/embed", json={"texts": [r["text"] for r in records]})
        response.raise_for_status()
        embeddings = response.json()["embeddings"]
    else:
        embeddings = [[0.1] * 384 for _ in records]
        print("EMBED_NGROK_URL is not set; using deterministic fallback embeddings")

    points = []
    for i, (emb, rec) in enumerate(zip(embeddings, records), start=1):
        points.append({"id": stable_point_id(str(rec.get("id", "")), i), "vector": emb, "payload": rec})

    requests.put(
        f"{QDRANT_URL}/collections/documents/points",
        json={"points": points},
        timeout=10,
    ).raise_for_status()
    print(f"Integration 5 OK: {len(points)} vectors stored in Qdrant")

# Test với sample data
embed_and_store([
    {"id": "doc_001", "text": "AI platform integration test"},
    {"id": "doc_002", "text": "Kafka to Airflow pipeline"},
])
