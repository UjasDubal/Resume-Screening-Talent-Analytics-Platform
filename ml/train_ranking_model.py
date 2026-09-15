"""
Ranking Model Training
========================
Trains a LogisticRegression model to rank candidate-job fit using three features:
  1. semantic_score (cosine similarity of text embeddings)
  2. skill_overlap_score (Jaccard similarity of skill sets)
  3. experience_score (normalized experience match)

Labeling Strategy (SIMULATED PROXY LABELS — NOT real hiring outcomes):
  - Label fit=1 if skill_overlap_score >= 0.5 AND experience_score >= 0.6
  - Label fit=0 otherwise
  - Then flip ~10% of labels randomly to simulate noise/imperfect ground truth
  This is a synthetic labeling heuristic used for demonstration purposes only.
  In production, labels would come from actual hiring decisions.

Train/Test Split:
  - GroupShuffleSplit grouped by candidate_id to prevent data leakage.
  - Same candidate never appears in both train and test sets.

Metrics:
  - ROC AUC on test set
  - NDCG@5 per job posting
  - Precision@5 per job posting
"""

import os
import json
import random
import sys

import numpy as np
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import roc_auc_score, ndcg_score


def generate_synthetic_labels(features: np.ndarray, noise_rate: float = 0.10) -> np.ndarray:
    """
    Generate synthetic proxy labels for training.

    SIMULATED PROXY LABEL: This is NOT real hiring outcome data.
    Label = 1 if skill_overlap_score >= 0.5 AND experience_score >= 0.6, else 0.
    Then ~10% of labels are randomly flipped to simulate noisy ground truth.

    Args:
        features: numpy array of shape (n, 3) with columns
                  [semantic_score, skill_overlap_score, experience_score]
        noise_rate: fraction of labels to randomly flip (default 0.10)

    Returns:
        numpy array of shape (n,) with binary labels.
    """
    skill_overlap = features[:, 1]
    experience = features[:, 2]

    labels = ((skill_overlap >= 0.5) & (experience >= 0.6)).astype(int)

    # Flip ~10% of labels to simulate noise
    n_flip = int(len(labels) * noise_rate)
    flip_indices = np.random.choice(len(labels), size=n_flip, replace=False)
    labels[flip_indices] = 1 - labels[flip_indices]

    return labels


def train_ranking_model(
    features: np.ndarray,
    labels: np.ndarray,
    candidate_ids: np.ndarray,
    test_size: float = 0.2,
    random_state: int = 42
) -> dict:
    """
    Train a LogisticRegression ranking model with proper train/test split.

    Args:
        features: numpy array of shape (n, 3)
        labels: numpy array of shape (n,) binary labels
        candidate_ids: numpy array of shape (n,) for grouping
        test_size: fraction of data for test set
        random_state: random seed

    Returns:
        dict with model, metrics, and split info.
    """
    np.random.seed(random_state)
    random.seed(random_state)

    # GroupShuffleSplit by candidate_id to prevent leakage
    gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_state)
    train_idx, test_idx = next(gss.split(features, labels, groups=candidate_ids))

    X_train, X_test = features[train_idx], features[test_idx]
    y_train, y_test = labels[train_idx], labels[test_idx]
    groups_train = candidate_ids[train_idx]
    groups_test = candidate_ids[test_idx]

    # ---- ASSERT: no candidate ID overlap between train and test ----
    train_ids = set(groups_train)
    test_ids = set(groups_test)
    overlap = train_ids & test_ids
    assert len(overlap) == 0, (
        f"Data leakage detected! {len(overlap)} candidate IDs appear in both "
        f"train and test sets: {overlap}"
    )
    print(f"[OK] No candidate ID overlap between train ({len(train_ids)} candidates) "
          f"and test ({len(test_ids)} candidates)")

    # Train LogisticRegression
    model = LogisticRegression(max_iter=1000, random_state=random_state)
    model.fit(X_train, y_train)

    # Predictions
    y_pred_proba = model.predict_proba(X_test)[:, 1]

    # ---- Metrics ----
    # ROC AUC
    auc = roc_auc_score(y_test, y_pred_proba)
    print(f"Test ROC AUC: {auc:.4f}")

    # NDCG and Precision@5 per job (approximated via grouping)
    # Since we don't have explicit job_ids here, we compute overall NDCG
    # Reshape for sklearn's ndcg_score (expects 2D)
    try:
        ndcg = ndcg_score(
            y_test.reshape(1, -1),
            y_pred_proba.reshape(1, -1),
            k=5
        )
        print(f"Test NDCG@5 (overall): {ndcg:.4f}")
    except Exception as e:
        ndcg = 0.0
        print(f"NDCG calculation error: {e}")

    # Precision@5
    top_5_idx = np.argsort(y_pred_proba)[-5:]
    precision_at_5 = np.mean(y_test[top_5_idx])
    print(f"Test Precision@5: {precision_at_5:.4f}")

    # Model coefficients
    feature_names = ["semantic_score", "skill_overlap_score", "experience_score"]
    coefs = dict(zip(feature_names, model.coef_[0]))
    print(f"Model coefficients: {coefs}")
    print(f"Model intercept: {model.intercept_[0]:.4f}")

    metrics = {
        "roc_auc": float(auc),
        "ndcg_at_5": float(ndcg),
        "precision_at_5": float(precision_at_5),
        "train_size": len(X_train),
        "test_size": len(X_test),
        "train_candidates": len(train_ids),
        "test_candidates": len(test_ids),
        "positive_rate_train": float(np.mean(y_train)),
        "positive_rate_test": float(np.mean(y_test)),
        "coefficients": {k: float(v) for k, v in coefs.items()},
        "intercept": float(model.intercept_[0]),
    }

    return {
        "model": model,
        "metrics": metrics,
        "train_idx": train_idx,
        "test_idx": test_idx,
    }


def save_model(model, filepath: str):
    """Save trained model to disk via joblib."""
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    joblib.dump(model, filepath)
    print(f"[OK] Model saved to {filepath}")


def load_model(filepath: str):
    """Load trained model from disk."""
    model = joblib.load(filepath)
    print(f"[OK] Model loaded from {filepath}")
    return model


def predict_scores(model, features: np.ndarray) -> np.ndarray:
    """
    Predict fit probability scores using the trained model.

    This replaces any hardcoded weighted_sum with model.predict_proba.

    Args:
        model: trained LogisticRegression model
        features: numpy array of shape (n, 3)

    Returns:
        numpy array of shape (n,) with probability scores in [0, 1].
    """
    return model.predict_proba(features)[:, 1]


def save_metrics(metrics: dict, filepath: str):
    """Save metrics to a JSON file."""
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"[OK] Metrics saved to {filepath}")


if __name__ == "__main__":
    # Demo with synthetic data
    print("=" * 60)
    print("Training Ranking Model (Demo with synthetic data)")
    print("=" * 60)

    np.random.seed(42)
    random.seed(42)

    # Simulate 500 candidate-job pairs
    n_samples = 500
    n_candidates = 50

    features = np.column_stack([
        np.random.uniform(0.1, 0.9, n_samples),  # semantic_score
        np.random.uniform(0.0, 1.0, n_samples),  # skill_overlap_score
        np.random.uniform(0.0, 1.0, n_samples),  # experience_score
    ])

    candidate_ids = np.random.choice(n_candidates, n_samples)
    labels = generate_synthetic_labels(features)

    print(f"\nDataset: {n_samples} pairs, {n_candidates} unique candidates")
    print(f"Positive rate: {np.mean(labels):.2%}")

    result = train_ranking_model(features, labels, candidate_ids)

    # Save
    model_dir = os.path.dirname(__file__)
    save_model(result["model"], os.path.join(model_dir, "model.pkl"))
    save_metrics(result["metrics"], os.path.join(model_dir, "metrics.json"))

    # Test predict
    test_features = features[:5]
    scores = predict_scores(result["model"], test_features)
    print(f"\nSample predictions: {scores}")
