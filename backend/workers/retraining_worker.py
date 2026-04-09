"""Nightly personalized-LSTM retraining job. Phase 3."""

# TODO(phase-3): Celery task that pulls the last 90 days of a user's sessions,
# fine-tunes the personalized LSTM head, registers in MLflow, and updates
# the serving pointer.
