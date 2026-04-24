"""Integration test fixtures — requires real model artifacts on disk."""

from __future__ import annotations

import os

import pytest

# Re-use the shared Kafka and Redis fakes from the parent conftest
# (they're autouse=True so they apply automatically).

# Check that model artifacts exist — skip the whole integration suite if not.
_lstm_path = os.path.join(
    os.path.dirname(__file__), "../../ml/lstm/artifacts/model.pt"
)
_xgb_path = os.path.join(
    os.path.dirname(__file__), "../../ml/xgboost/artifacts/model.json"
)

if not os.path.exists(_lstm_path) or not os.path.exists(_xgb_path):
    pytest.skip(
        "Model artifacts not found — run training first",
        allow_module_level=True,
    )

# Also skip if RUN_INTEGRATION is not set (these are slow — opt-in only)
if not os.environ.get("RUN_INTEGRATION"):
    pytest.skip(
        "Integration tests skipped — set RUN_INTEGRATION=1 to enable (takes ~10min at full scale)",
        allow_module_level=True,
    )
