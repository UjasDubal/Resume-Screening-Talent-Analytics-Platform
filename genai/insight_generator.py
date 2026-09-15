"""
GenAI Candidate Insights Generator
====================================
Generates natural-language candidate insights using Groq API (free-tier Llama model),
with a deterministic offline fallback when GROQ_API_KEY is not set or API fails.

Model: llama-3.3-70b-versatile (with fallback to llama-3.1-8b-instant)
"""

import os
import json
from typing import Optional, Dict, Any

# Primary and fallback Groq models (active for this API key)
PRIMARY_MODEL = os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b")
FALLBACK_MODEL = "groq/compound-mini"
ALTERNATIVE_MODELS = ["qwen/qwen3.8-27b", "groq/compound-mini", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]


def generate_offline_insight(
    candidate_name: str,
    job_title: str,
    final_score: float,
    features: Dict[str, float],
    candidate_skills: Optional[list] = None,
    required_skills: Optional[list] = None,
    candidate_experience: Optional[float] = None,
    required_experience: Optional[float] = None,
) -> str:
    """
    Generate a deterministic templated explanation without external API calls.
    Used when GROQ_API_KEY is missing, network is unavailable, or rate limit is hit.
    """
    candidate_skills = candidate_skills or []
    required_skills = required_skills or []
    cand_set = {s.lower().strip() for s in candidate_skills}
    req_set = {s.lower().strip() for s in required_skills}

    matching_skills = [s for s in candidate_skills if s.lower().strip() in req_set]
    missing_skills = [s for s in required_skills if s.lower().strip() not in cand_set]

    sem = features.get("semantic_score", 0.0)
    skill_score = features.get("skill_overlap_score", 0.0)
    exp_score = features.get("experience_score", 0.0)

    # Determine primary driver
    score_map = {
        "strong skill overlap": skill_score,
        "high semantic background match": sem,
        "aligned experience duration": exp_score,
    }
    top_driver = max(score_map, key=score_map.get)

    match_pct = round(final_score * 100, 1)

    # Construct clean template
    explanation = f"[Offline Mode] Candidate has a {match_pct}% fit score for {job_title}, driven primarily by {top_driver}."

    if matching_skills:
        explanation += f" Demonstrates key overlap in: {', '.join(matching_skills[:4])}."
    else:
        explanation += f" Background provides transferrable skills for this position."

    if missing_skills:
        explanation += f" Area for growth: candidate lacks direct experience with {', '.join(missing_skills[:2])}."
    elif candidate_experience is not None and required_experience is not None:
        if candidate_experience < required_experience:
            diff = required_experience - candidate_experience
            explanation += f" Experience gap: {candidate_experience:.0f} years vs {required_experience:.0f} years required ({diff:.0f} year delta)."
        else:
            explanation += f" Candidate exceeds the required {required_experience:.0f} years of experience with {candidate_experience:.0f} years recorded."
    else:
        explanation += " Candidate meets all explicitly listed prerequisites."

    return explanation


def generate_groq_insight(
    candidate_name: str,
    job_title: str,
    job_department: str,
    final_score: float,
    features: Dict[str, float],
    candidate_skills: list,
    required_skills: list,
    candidate_experience: float,
    required_experience: float,
    candidate_summary: str = "",
    api_key: Optional[str] = None,
) -> str:
    """
    Call Groq Chat Completion API to generate 2-3 sentence fit explanation + 1 gap.
    """
    api_key = api_key or os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GROQ_API_KEY is not configured.")

    from groq import Groq

    client = Groq(api_key=api_key)

    prompt = f"""You are an expert talent acquisition consultant.
Evaluate the candidate's match for this position in 2-3 concise sentences explaining why they are a good fit, followed by 1 concise sentence highlighting an actionable gap or area of development.

Candidate: {candidate_name}
Summary: {candidate_summary}
Candidate Skills: {', '.join(candidate_skills)}
Candidate Experience: {candidate_experience} years

Target Job: {job_title} ({job_department})
Required Skills: {', '.join(required_skills)}
Required Experience: {required_experience} years

Match Metrics:
- Semantic Alignment Score: {features.get('semantic_score', 0):.2f} / 1.00
- Skill Overlap Score: {features.get('skill_overlap_score', 0):.2f} / 1.00
- Experience Alignment Score: {features.get('experience_score', 0):.2f} / 1.00
- Final Predicted Fit Score: {final_score:.2f} / 1.00

Write 3 to 4 sentences total. Be direct, professional, and specific. Do not use generic filler."""

    for model_name in ALTERNATIVE_MODELS:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a professional talent acquisition consultant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=250,
            )
            content = response.choices[0].message.content.strip() if response.choices else ""
            if content:
                return content
        except Exception as err:
            print(f"  [WARN] Groq model '{model_name}' call failed: {err}")
            continue

    raise RuntimeError("All configured Groq models failed.")


_groq_disabled = False


def generate_candidate_insight(
    candidate_name: str,
    job_title: str,
    job_department: str = "",
    final_score: float = 0.0,
    features: Optional[Dict[str, float]] = None,
    candidate_skills: Optional[list] = None,
    required_skills: Optional[list] = None,
    candidate_experience: float = 0.0,
    required_experience: float = 0.0,
    candidate_summary: str = "",
    api_key: Optional[str] = None,
) -> str:
    """
    Main entry point for generating candidate insights.
    Safely catches any API/network/rate-limit error and returns an offline fallback.
    """
    global _groq_disabled
    features = features or {"semantic_score": 0.0, "skill_overlap_score": 0.0, "experience_score": 0.0}
    candidate_skills = candidate_skills or []
    required_skills = required_skills or []

    key = api_key or os.environ.get("GROQ_API_KEY", "").strip()

    if key and not _groq_disabled:
        try:
            return generate_groq_insight(
                candidate_name=candidate_name,
                job_title=job_title,
                job_department=job_department,
                final_score=final_score,
                features=features,
                candidate_skills=candidate_skills,
                required_skills=required_skills,
                candidate_experience=candidate_experience,
                required_experience=required_experience,
                candidate_summary=candidate_summary,
                api_key=key,
            )
        except Exception as e:
            _groq_disabled = True
            print(f"  [INFO] Groq API unavailable ({e}). Tripping circuit breaker and switching to fast offline engine.")

    return generate_offline_insight(
        candidate_name=candidate_name,
        job_title=job_title,
        final_score=final_score,
        features=features,
        candidate_skills=candidate_skills,
        required_skills=required_skills,
        candidate_experience=candidate_experience,
        required_experience=required_experience,
    )


if __name__ == "__main__":
    # Test offline insight
    sample_features = {"semantic_score": 0.85, "skill_overlap_score": 0.75, "experience_score": 0.90}
    cand_skills = ["Python", "Django", "PostgreSQL", "Docker"]
    req_skills = ["Python", "Django", "PostgreSQL", "Kubernetes", "AWS"]

    print("--- Testing Offline Mode ---")
    offline_result = generate_candidate_insight(
        candidate_name="Alex Turner",
        job_title="Senior Backend Engineer",
        job_department="Engineering",
        final_score=0.82,
        features=sample_features,
        candidate_skills=cand_skills,
        required_skills=req_skills,
        candidate_experience=4.0,
        required_experience=5.0,
    )
    print(offline_result)
