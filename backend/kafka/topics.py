"""Kafka topic names — centralized so a typo can't fork producer/consumer."""

SESSION_EVENTS_RAW = "session.events.raw"
TRANSACTION_EVENTS_RAW = "transaction.events.raw"
SESSION_FEATURES = "session.features.computed"
TRANSACTION_FEATURES = "transaction.features.computed"
SCORES_BEHAVIORAL = "scores.behavioral"
SCORES_CONTEXT = "scores.context"
SCORES_FINAL = "scores.final"
FRICTION_DECISIONS = "friction.decisions"

ALL_TOPICS: tuple[str, ...] = (
    SESSION_EVENTS_RAW,
    TRANSACTION_EVENTS_RAW,
    SESSION_FEATURES,
    TRANSACTION_FEATURES,
    SCORES_BEHAVIORAL,
    SCORES_CONTEXT,
    SCORES_FINAL,
    FRICTION_DECISIONS,
)
