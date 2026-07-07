import json
import subprocess
import time

import redis
import requests


QDRANT_URL = "http://localhost:6333"


def run(command: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, check=check)


def wait_for_http(url: str, name: str, timeout_s: int = 90) -> None:
    deadline = time.time() + timeout_s
    last_error = ""
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=3)
            if response.status_code < 500:
                print(f"[OK] {name} ready")
                return
            last_error = f"HTTP {response.status_code}"
        except requests.RequestException as exc:
            last_error = str(exc)
        time.sleep(3)
    raise RuntimeError(f"{name} not ready: {last_error}")


def create_kafka_topic() -> None:
    result = run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "kafka",
            "kafka-topics",
            "--create",
            "--if-not-exists",
            "--topic",
            "data.raw",
            "--bootstrap-server",
            "localhost:9092",
            "--partitions",
            "1",
            "--replication-factor",
            "1",
        ]
    )
    print(result.stdout.strip() or "[OK] Kafka topic data.raw exists")


def create_qdrant_collection() -> None:
    response = requests.put(
        f"{QDRANT_URL}/collections/documents",
        json={"vectors": {"size": 384, "distance": "Cosine"}},
        timeout=10,
    )
    if response.status_code != 409:
        response.raise_for_status()
    points = [
        {
            "id": 1,
            "vector": [0.1] * 384,
            "payload": {"id": "doc_001", "text": "AI platform integration test"},
        },
        {
            "id": 2,
            "vector": [0.2] * 384,
            "payload": {"id": "doc_002", "text": "Kafka to Delta to Feast pipeline"},
        },
    ]
    response = requests.put(
        f"{QDRANT_URL}/collections/documents/points",
        json={"points": points},
        timeout=10,
    )
    response.raise_for_status()
    print("[OK] Qdrant collection documents seeded")


def seed_redis_features() -> None:
    client = redis.Redis(host="localhost", port=6379, decode_responses=True)
    client.set(
        "feature:doc_001",
        json.dumps(
            {
                "text": "AI platform integration test",
                "timestamp": time.time(),
                "processed": True,
            }
        ),
    )
    print("[OK] Redis feature store seeded")


if __name__ == "__main__":
    wait_for_http("http://localhost:8000/health", "API Gateway")
    wait_for_http("http://localhost:6333/healthz", "Qdrant")
    wait_for_http("http://localhost:9090/-/healthy", "Prometheus")
    create_kafka_topic()
    create_qdrant_collection()
    seed_redis_features()
    print("Bootstrap complete")
