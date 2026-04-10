"""Kafka consumer — drives event_handlers over the raw topics.

Run:
    python -m backend.workers.kafka_consumer

Design:
- Single consumer group `allgreen-ingest`, manual offset commits after DB write.
- At-least-once. Duplicates on session_events are tolerable — the feature
  extractor groups by (session_id, ts_ms) so a double-insert only widens the
  window, it doesn't corrupt features.
- confluent_kafka is lazy-imported inside build_consumer() so unit tests can
  import this module without librdkafka installed.
"""

from __future__ import annotations

import signal
from typing import Any

import orjson
import structlog

from backend.db.session import SessionLocal
from backend.kafka import topics
from backend.logging_setup import configure_logging
from backend.workers.event_handlers import (
    handle_session_events,
    handle_transaction,
)

configure_logging()
log = structlog.get_logger()

SUBSCRIBE_TO = [topics.SESSION_EVENTS_RAW, topics.TRANSACTION_EVENTS_RAW]


def build_consumer() -> Any:
    from confluent_kafka import Consumer  # type: ignore[import-not-found]

    from backend.config import get_settings

    settings = get_settings()
    return Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": "allgreen-ingest",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
            "max.poll.interval.ms": 300000,
        }
    )


def _process_one(topic: str, payload: dict) -> None:
    db = SessionLocal()
    try:
        if topic == topics.SESSION_EVENTS_RAW:
            n = handle_session_events(db, payload)
            log.debug("consumer.session.persisted", count=n)
        elif topic == topics.TRANSACTION_EVENTS_RAW:
            handle_transaction(db, payload)
            log.debug("consumer.tx.persisted")
        else:
            log.warning("consumer.unknown_topic", topic=topic)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run() -> int:
    from confluent_kafka import KafkaException  # type: ignore[import-not-found]

    consumer = build_consumer()
    consumer.subscribe(SUBSCRIBE_TO)
    log.info("consumer.start", topics=SUBSCRIBE_TO)

    stop = False

    def _signal(signum, _frame):  # noqa: ANN001
        nonlocal stop
        log.info("consumer.signal", signum=signum)
        stop = True

    signal.signal(signal.SIGINT, _signal)
    signal.signal(signal.SIGTERM, _signal)

    try:
        while not stop:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                raise KafkaException(msg.error())

            try:
                payload = orjson.loads(msg.value())
            except orjson.JSONDecodeError:
                log.warning("consumer.bad_json", topic=msg.topic(), offset=msg.offset())
                consumer.commit(msg)
                continue

            try:
                _process_one(msg.topic(), payload)
                consumer.commit(msg)
            except Exception:
                log.exception(
                    "consumer.handler_failed",
                    topic=msg.topic(),
                    offset=msg.offset(),
                )
                # Don't commit — leave for retry on the next poll.
    finally:
        consumer.close()
        log.info("consumer.stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
