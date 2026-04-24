"""Nightly personalized-LSTM retraining job."""

# TODO: Celery task that pulls the last 90 days of a user's sessions,
# fine-tunes the personalized LSTM head, registers in MLflow, and updates
# the serving pointer.
