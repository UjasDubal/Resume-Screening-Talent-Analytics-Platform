"""
Unit Tests for Ranking Model Module
=====================================
Tests:
  - Zero candidate ID leakage between train and test splits (GroupShuffleSplit verification)
  - Synthetic label generation properties
  - Prediction scores strictly bounded in [0.0, 1.0]
  - Model serialization and deserialization reproducibility
"""

import os
import tempfile
import pytest
import numpy as np

from ml.train_ranking_model import (
    generate_synthetic_labels,
    train_ranking_model,
    save_model,
    load_model,
    predict_scores
)


@pytest.fixture
def dummy_dataset():
    """Create a reproducible synthetic dataset for testing."""
    np.random.seed(42)
    n_samples = 300
    n_candidates = 30

    features = np.column_stack([
        np.random.uniform(0.2, 0.9, n_samples),
        np.random.uniform(0.0, 1.0, n_samples),
        np.random.uniform(0.0, 1.0, n_samples),
    ])
    candidate_ids = np.random.choice(n_candidates, n_samples)
    labels = generate_synthetic_labels(features)

    return features, labels, candidate_ids


def test_zero_candidate_id_leakage(dummy_dataset):
    """
    CRITICAL: Assert that no candidate ID appears in both the train and test splits.
    Prevents data leakage in the talent matching evaluation.
    """
    features, labels, candidate_ids = dummy_dataset

    result = train_ranking_model(features, labels, candidate_ids, test_size=0.2, random_state=42)

    train_ids = set(candidate_ids[result["train_idx"]])
    test_ids = set(candidate_ids[result["test_idx"]])

    overlap = train_ids.intersection(test_ids)
    assert len(overlap) == 0, f"Data leakage detected! Candidate IDs in both sets: {overlap}"
    assert len(train_ids) > 0
    assert len(test_ids) > 0


def test_synthetic_labels_properties(dummy_dataset):
    """Synthetic labels should only be 0 or 1, with a non-zero positive rate."""
    features, labels, _ = dummy_dataset
    unique_vals = set(np.unique(labels))
    assert unique_vals.issubset({0, 1})
    assert 0.05 < np.mean(labels) < 0.95


def test_predict_scores_bounds(dummy_dataset):
    """Model predictions should be valid probabilities in [0.0, 1.0]."""
    features, labels, candidate_ids = dummy_dataset
    result = train_ranking_model(features, labels, candidate_ids, test_size=0.2, random_state=42)
    model = result["model"]

    preds = predict_scores(model, features)
    assert len(preds) == len(features)
    assert np.all(preds >= 0.0)
    assert np.all(preds <= 1.0)


def test_model_serialization_reproducibility(dummy_dataset, tmp_path):
    """Saving and reloading the model should yield identical prediction probabilities."""
    features, labels, candidate_ids = dummy_dataset
    result = train_ranking_model(features, labels, candidate_ids, test_size=0.2, random_state=42)
    original_model = result["model"]

    model_file = str(tmp_path / "test_model.pkl")
    save_model(original_model, model_file)

    loaded_model = load_model(model_file)

    orig_preds = predict_scores(original_model, features[:20])
    loaded_preds = predict_scores(loaded_model, features[:20])

    np.testing.assert_allclose(orig_preds, loaded_preds, rtol=1e-5)
