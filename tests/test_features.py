"""
Unit Tests for Feature Engineering Module
===========================================
Tests:
  - skill_overlap_score: identical sets, disjoint sets, partial overlap, case insensitivity, empty sets
  - experience_score: exact match, under-experienced, over-experienced, zero required years
  - semantic_score: similarity scores clamped to [0, 1]
  - compute_all_features: combined feature dictionary integrity
"""

import pytest
import numpy as np
from ml.features import (
    skill_overlap_score, experience_score, semantic_score, compute_all_features
)


def test_skill_overlap_identical():
    """Identical skill sets should yield a Jaccard score of 1.0."""
    skills = ["Python", "SQL", "Docker"]
    assert skill_overlap_score(skills, skills) == pytest.approx(1.0)


def test_skill_overlap_disjoint():
    """Disjoint skill sets should yield 0.0."""
    cand = ["Python", "Django"]
    req = ["Figma", "User Research"]
    assert skill_overlap_score(cand, req) == pytest.approx(0.0)


def test_skill_overlap_partial_and_casing():
    """Partial overlap should calculate exact Jaccard similarity and ignore casing/spaces."""
    cand = ["python ", "SQL", "Docker", "AWS"]
    req = ["PYTHON", "sql", "Kubernetes"]
    # Intersection: {python, sql} (size 2)
    # Union: {python, sql, docker, aws, kubernetes} (size 5)
    # Jaccard = 2 / 5 = 0.4
    assert skill_overlap_score(cand, req) == pytest.approx(0.4)


def test_skill_overlap_empty_sets():
    """Empty sets should safely return 0.0 without ZeroDivisionError."""
    assert skill_overlap_score([], []) == 0.0
    assert skill_overlap_score(["Python"], []) == 0.0
    assert skill_overlap_score([], ["SQL"]) == 0.0


def test_experience_exact_match():
    """Exact experience match should yield 1.0."""
    assert experience_score(5.0, 5.0) == pytest.approx(1.0)
    assert experience_score(1.0, 1.0) == pytest.approx(1.0)


def test_experience_under_and_over():
    """Test experience score under- and over-qualification penalties."""
    # 3 years vs 5 required: 1 - |3 - 5| / 5 = 1 - 2/5 = 0.6
    assert experience_score(3.0, 5.0) == pytest.approx(0.6)

    # 7 years vs 5 required: 1 - |7 - 5| / 5 = 1 - 2/5 = 0.6
    assert experience_score(7.0, 5.0) == pytest.approx(0.6)

    # 0 years vs 5 required: 1 - |0 - 5| / 5 = 0.0
    assert experience_score(0.0, 5.0) == pytest.approx(0.0)

    # Far under: should clamp to 0.0, never negative
    assert experience_score(1.0, 10.0) >= 0.0


def test_experience_zero_required():
    """Zero required years means candidate automatically qualifies (1.0)."""
    assert experience_score(3.0, 0.0) == pytest.approx(1.0)
    assert experience_score(0.0, 0.0) == pytest.approx(1.0)


def test_semantic_score_bounds():
    """Semantic similarity scores should always be bounded in [0.0, 1.0]."""
    score = semantic_score("Senior Python Software Engineer", "Python Backend Developer")
    assert 0.0 <= score <= 1.0
    assert score > 0.4  # Similar roles should have high similarity

    disjoint_score = semantic_score("Sales Representative Cold Calling", "Deep Learning Research Scientist")
    assert 0.0 <= disjoint_score <= 1.0
    assert score > disjoint_score  # Related roles score higher than unrelated


def test_compute_all_features():
    """compute_all_features should return a dictionary with all three keys."""
    res = compute_all_features(
        resume_text="Senior Data Analyst with SQL and Python",
        job_text="Hiring Data Analyst proficient in SQL",
        candidate_skills=["SQL", "Python"],
        required_skills=["SQL", "Tableau"],
        candidate_years=4.0,
        required_years=3.0,
    )
    assert "semantic_score" in res
    assert "skill_overlap_score" in res
    assert "experience_score" in res
    for val in res.values():
        assert 0.0 <= val <= 1.0
