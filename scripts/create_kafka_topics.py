"""Create the Kafka topics we need.

Run once after the kafka broker is up:

    python scripts/create_kafka_topics.py

Idempotent — existing topics are skipped. 8 partitions per topic;
RF=1 in dev (bumped in prod via terraform).
"""

from __future__ import annotations

import sys

from confluent_kafka.admin import AdminClient, NewTopic

from backend.config import get_settings

TOPICS: list[tuple[str, int]] = [
    ("session.events.raw", 8),
    ("transaction.events.raw", 8),
    ("session.features.computed", 8),
    ("transaction.features.computed", 8),
    ("scores.behavioral", 8),
    ("scores.context", 8),
    ("scores.final", 8),
    ("friction.decisions", 8),
]


def main() -> int:
    settings = get_settings()
    admin = AdminClient({"bootstrap.servers": settings.kafka_bootstrap_servers})

    existing = set(admin.list_topics(timeout=10).topics.keys())
    to_create = [
        NewTopic(name, num_partitions=parts, replication_factor=1)
        for name, parts in TOPICS
        if name not in existing
    ]

    if not to_create:
        print("all topics already exist, nothing to do")
        return 0

    futures = admin.create_topics(to_create)
    rc = 0
    for name, fut in futures.items():
        try:
            fut.result()
            print(f"created: {name}")
        except Exception as exc:  # noqa: BLE001
            print(f"failed:  {name} — {exc}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
