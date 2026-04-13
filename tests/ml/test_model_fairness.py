"""Model fairness checks.

Blueprint §12: "Ensure false positive rate is equal across age groups and
geographic regions."

Phase 3 reality check: our synthetic data doesn't have demographic attributes,
so we can't do real fairness testing yet. What we *can* do is verify that the
models don't produce wildly different FPR across random subsets of the normal
population — which is a proxy for "no group is systematically disadvantaged by
feature noise." Real fairness testing with protected attributes happens in
phase 6 when we get labeled data from the bank.
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.models.lstm_inference import score_session
from tests.data_generator import build_training_dataset


@pytest.fixture(scope="module")
def normal_scores():
    """Score the normal-only holdout."""
    X, y = build_training_dataset(n_normal=200, n_fraud=0, seed=777)
    scores = np.array([score_session(X[i]) for i in range(len(y))])
    return scores


def test_fpr_variance_across_random_groups(normal_scores) -> None:
    """Split normals into 4 arbitrary groups, check FPR doesn't vary > 10pp."""
    np.random.seed(42)
    indices = np.arange(len(normal_scores))
    np.random.shuffle(indices)
    groups = np.array_split(indices, 4)

    fprs = []
    for g in groups:
        group_scores = normal_scores[g]
        fpr = (group_scores >= 0.5).sum() / len(group_scores)
        fprs.append(fpr)

    spread = max(fprs) - min(fprs)
    print(f"FPR across 4 groups: {fprs} | spread: {spread:.4f}")
    assert spread < 0.10, (
        f"FPR spread {spread:.2%} is too wide (>10pp). "
        "Model may be sensitive to feature noise in a biased way."
    )
