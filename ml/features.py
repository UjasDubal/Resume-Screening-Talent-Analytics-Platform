"""
Feature Engineering
====================
Computes three matching features for candidate-job pairs:
  1. semantic_score — cosine similarity of MiniLM embeddings
  2. skill_overlap_score — Jaccard similarity of skill sets
  3. experience_score — normalized fit of candidate's years vs. required years
"""

import os
import sys
import numpy as np

try:
    from ml.embeddings import get_embedding, cosine_similarity
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from ml.embeddings import get_embedding, cosine_similarity


def semantic_score(resume_text: str, job_text: str) -> float:
    """
    Compute semantic similarity between resume text and job description.

    Uses all-MiniLM-L6-v2 embeddings and cosine similarity.

    Args:
        resume_text: Full resume text or summary.
        job_text: Full job description text.

    Returns:
        Float in [0, 1] (cosine similarity, typically positive for text).
    """
    resume_emb = get_embedding(resume_text)
    job_emb = get_embedding(job_text)
    score = cosine_similarity(resume_emb, job_emb)
    return max(0.0, score)  # Clamp to [0, 1]


def skill_overlap_score(candidate_skills: list, required_skills: list) -> float:
    """
    Compute Jaccard similarity between candidate and required skill sets.

    Jaccard = |intersection| / |union|

    Args:
        candidate_skills: List of skills the candidate has.
        required_skills: List of skills required by the job.

    Returns:
        Float in [0, 1]. Returns 0.0 if both sets are empty.
    """
    if not candidate_skills and not required_skills:
        return 0.0

    # Normalize to lowercase for case-insensitive matching
    cand_set = {s.lower().strip() for s in candidate_skills}
    req_set = {s.lower().strip() for s in required_skills}

    intersection = cand_set & req_set
    union = cand_set | req_set

    if not union:
        return 0.0

    return len(intersection) / len(union)


def experience_score(candidate_years: float, required_years: float) -> float:
    """
    Compute experience match score.

    Formula: 1 - |candidate_years - required_years| / max(required_years, 1)
    Clamped to [0, 1].

    Candidates with more experience than required get a slight penalty but
    not as severe as under-qualified candidates.

    Args:
        candidate_years: Years of experience the candidate has.
        required_years: Years of experience required by the job.

    Returns:
        Float in [0, 1].
    """
    candidate_years = float(candidate_years or 0.0)
    required_years = float(required_years or 0.0)
    if required_years <= 0:
        # No requirement specified — everyone qualifies
        return 1.0

    diff = abs(candidate_years - required_years)
    score = 1.0 - diff / max(required_years, 1.0)
    return max(0.0, min(1.0, float(score)))


def compute_all_features(
    resume_text: str,
    job_text: str,
    candidate_skills: list,
    required_skills: list,
    candidate_years: float,
    required_years: float
) -> dict:
    """
    Compute all three features for a candidate-job pair.

    Returns:
        {
            "semantic_score": float,
            "skill_overlap_score": float,
            "experience_score": float,
        }
    """
    return {
        "semantic_score": semantic_score(resume_text, job_text),
        "skill_overlap_score": skill_overlap_score(candidate_skills, required_skills),
        "experience_score": experience_score(candidate_years, required_years),
    }


if __name__ == "__main__":
    # Quick test
    print("Testing feature computations...")

    # Skill overlap
    cand_skills = ["Python", "Django", "PostgreSQL", "Docker", "Git"]
    req_skills = ["Python", "Django", "PostgreSQL", "REST APIs", "AWS"]
    overlap = skill_overlap_score(cand_skills, req_skills)
    print(f"Skill overlap: {overlap:.4f}")

    # Experience
    for cand_yrs, req_yrs in [(5, 5), (3, 5), (8, 5), (0, 3), (5, 0)]:
        score = experience_score(cand_yrs, req_yrs)
        print(f"Experience({cand_yrs} vs {req_yrs}): {score:.4f}")

    # Semantic (requires model download)
    sem = semantic_score(
        "Senior Python developer experienced with Django and PostgreSQL databases",
        "Looking for a backend engineer proficient in Python and SQL databases"
    )
    print(f"Semantic score: {sem:.4f}")
