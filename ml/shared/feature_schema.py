"""Single source of truth for feature names across training + serving.

Re-exports from backend.features so we don't end up with two drifting copies.
"""

from backend.features.session_extractor import BEHAVIORAL_FEATURE_NAMES
from backend.features.transaction_extractor import TRANSACTION_FEATURE_NAMES

__all__ = ["BEHAVIORAL_FEATURE_NAMES", "TRANSACTION_FEATURE_NAMES"]
