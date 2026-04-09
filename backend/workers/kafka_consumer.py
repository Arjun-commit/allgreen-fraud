"""Kafka consumer — session + transaction events into the DB / feature store.

Phase 2. For now it's a skeleton that you can run to verify the broker
connection works end-to-end.

    python -m backend.workers.kafka_consumer
"""

from __future__ import annotations

import signal
import sys

import structlog
from confluent_kafka import Consumer, KafkaException

from backend.config import get_settings
from backend.logging_setup import configure_logging

configure_logging()
log = structlog.get_logger()


TOPICS = ["session.events.raw", "transaction.events.raw"]


def build_consumer() -> Consumer:
    settings = get_settings()
    return Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": "allgreen-ingest",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )


def run() -> int:
    consumer = build_consumer()
    consumer.subscribe(TOPICS)

    stop = False

    def _handle_signal(signum, frame):  # noqa: ANN001
        nonlocal stop
        log.info("consumer.signal", signum=signum)
        stop = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    log.info("consumer.start", topics=TOPICS)
    try:
        while not stop:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                raise KafkaException(msg.error())

            # TODO(phase-2): decode JSON, route by topic, persist.
            log.debug(
                "consumer.msg",
                topic=msg.topic(),
                partition=msg.partition(),
                offset=msg.offset(),
            )
            consumer.commit(msg)
    finally:
        consumer.close()
        log.info("consumer.stopped")
    return 0


if __name__ == "__main__":
    sys.exit(run())
