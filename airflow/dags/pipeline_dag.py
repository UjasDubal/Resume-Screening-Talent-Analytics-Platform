"""
Apache Airflow Pipeline DAG
============================
Orchestrates the end-to-end talent analytics workflow:
  1. check_or_generate_synthetic_data (conditional/manual)
  2. parse_resumes (pdfplumber + PyMuPDF fallback + docx)
  3. extract_entities_and_load_warehouse (spaCy NER + Postgres dim/bridge tables)
  4. compute_features_and_train_ranking (embeddings + features + LogisticRegression)
  5. generate_insights_and_load_facts (Groq GenAI / offline fallback + fact_applications)
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

# 1. Import Airflow first (before modifying sys.path to avoid shadowing with local airflow/ directory)
try:
    from airflow import DAG  # type: ignore
    from airflow.operators.python import PythonOperator  # type: ignore
    AIRFLOW_AVAILABLE = True
except ImportError:
    AIRFLOW_AVAILABLE = False
    DAG = None
    PythonOperator = None

# 2. Configure project root (supports both Docker container /opt/airflow/project and local workspace)
if os.path.exists("/opt/airflow/project"):
    PROJECT_ROOT = "/opt/airflow/project"
else:
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)


default_args = {
    "owner": "kdac2",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}


# ---------------------------------------------------------------------------
# Task 1: Check or Generate Data
# ---------------------------------------------------------------------------
def task_check_or_gen_data(**context):
    """Ensure raw resumes and synthetic jobs exist; generate if missing."""
    import synth.generate_jobs as gj
    import synth.generate_resumes as gr

    data_dir = os.path.join(PROJECT_ROOT, "data")
    resumes_dir = os.path.join(data_dir, "raw_resumes")
    jobs_file = os.path.join(data_dir, "synthetic_jobs.json")

    os.makedirs(resumes_dir, exist_ok=True)

    # 1. Job descriptions
    if not os.path.exists(jobs_file):
        print("Generating synthetic job descriptions...")
        gj.generate_jobs(jobs_file)
    else:
        print(f"Jobs file already exists at {jobs_file}")

    # 2. Resumes
    existing_resumes = [f for f in os.listdir(resumes_dir) if f.endswith((".pdf", ".docx"))]
    if len(existing_resumes) < 20:
        print(f"Generating synthetic resumes (found {len(existing_resumes)})...")
        gr.generate_resumes(resumes_dir, count=150)
    else:
        print(f"Found {len(existing_resumes)} existing resume files in {resumes_dir}")

    return {"jobs_file": jobs_file, "resumes_count": len(os.listdir(resumes_dir))}


# ---------------------------------------------------------------------------
# Task 2: Parse Resumes
# ---------------------------------------------------------------------------
def task_parse_resumes(**context):
    """Parse raw PDF/DOCX resumes into structured dicts."""
    from etl.parser import parse_file

    resumes_dir = os.path.join(PROJECT_ROOT, "data", "raw_resumes")
    parsed_cache_file = os.path.join(PROJECT_ROOT, "data", "parsed_resumes.json")

    files = sorted([
        os.path.join(resumes_dir, f) for f in os.listdir(resumes_dir)
        if f.lower().endswith((".pdf", ".docx"))
    ])

    parsed_records = []
    print(f"Parsing {len(files)} files...")
    for i, filepath in enumerate(files, 1):
        try:
            record = parse_file(filepath)
            parsed_records.append(record)
        except Exception as e:
            print(f"Failed to parse {os.path.basename(filepath)}: {e}")

    with open(parsed_cache_file, "w", encoding="utf-8") as f:
        json.dump(parsed_records, f, indent=2)

    print(f"Saved {len(parsed_records)} parsed records to {parsed_cache_file}")
    return len(parsed_records)


# ---------------------------------------------------------------------------
# Task 3: NER Extract & Warehouse Load (Dims & Bridge)
# ---------------------------------------------------------------------------
def task_extract_and_load_dims(**context):
    """Run spaCy NER and load dim_candidate, dim_skill, dim_job, bridge."""
    from etl.ner_extract import extract_from_text
    from etl.load_warehouse import (
        get_db_connection, load_skills, load_candidates, load_jobs, clear_all_data
    )

    parsed_cache_file = os.path.join(PROJECT_ROOT, "data", "parsed_resumes.json")
    jobs_file = os.path.join(PROJECT_ROOT, "data", "synthetic_jobs.json")

    with open(parsed_cache_file, "r", encoding="utf-8") as f:
        parsed_records = json.load(f)

    # Extract entities
    print(f"Extracting entities for {len(parsed_records)} resumes...")
    candidates = []
    all_skills = set()

    for rec in parsed_records:
        extracted = extract_from_text(rec["raw_text"], source_file=rec.get("source_file", ""))
        cand = {
            "name": extracted["name"],
            "education": extracted["education"],
            "university": "",
            "experience_years": extracted["experience_years"],
            "location": "",
            "most_recent_title": extracted["most_recent_title"],
            "job_family": "",
            "source_file": rec["source_file"],
            "skills": extracted["skills"],
            "raw_text": rec["raw_text"],
        }
        candidates.append(cand)
        all_skills.update(extracted["skills"])

    # Load into Postgres
    conn = get_db_connection()
    clear_all_data(conn)

    # 1. Skills
    skill_map = load_skills(conn, list(all_skills))
    print(f"Loaded {len(skill_map)} unique skills.")

    # 2. Candidates + Bridge
    file_to_id = load_candidates(conn, candidates, skill_map)
    print(f"Loaded {len(file_to_id)} candidates and associations.")

    # 3. Jobs
    job_ids = load_jobs(conn, jobs_file)
    print(f"Loaded {len(job_ids)} jobs.")

    conn.close()

    # Save candidates with IDs for ML matching task
    cand_cache = os.path.join(PROJECT_ROOT, "data", "extracted_candidates.json")
    for c in candidates:
        c["candidate_id"] = file_to_id.get(c["source_file"])

    with open(cand_cache, "w", encoding="utf-8") as f:
        json.dump(candidates, f, indent=2)

    return {"candidates_loaded": len(candidates), "jobs_loaded": len(job_ids)}


# ---------------------------------------------------------------------------
# Task 4: Match, Rank, Generate Insights & Populate Fact Table
# ---------------------------------------------------------------------------
def task_match_rank_and_load_facts(**context):
    """Compute features, run ranking model inference, generate insights, populate fact_applications."""
    import numpy as np
    from ml.features import semantic_score, skill_overlap_score, experience_score
    from ml.train_ranking_model import (
        generate_synthetic_labels, train_ranking_model, save_model, load_model, predict_scores
    )
    from genai.insight_generator import generate_candidate_insight
    from etl.load_warehouse import get_db_connection, load_fact_applications

    cand_cache = os.path.join(PROJECT_ROOT, "data", "extracted_candidates.json")
    jobs_file = os.path.join(PROJECT_ROOT, "data", "synthetic_jobs.json")
    model_path = os.path.join(PROJECT_ROOT, "ml", "model.pkl")

    with open(cand_cache, "r", encoding="utf-8") as f:
        candidates = json.load(f)

    # Fetch jobs directly from dim_job in database to guarantee job_id foreign key alignment
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT job_id, title, department, company, location, job_family,
               required_skills, required_experience, description
        FROM dim_job
        ORDER BY job_id
    """)
    jobs = [
        {
            "job_id": row[0],
            "title": row[1],
            "department": row[2],
            "company": row[3],
            "location": row[4],
            "job_family": row[5],
            "required_skills": row[6] or [],
            "required_experience": float(row[7] or 0.0),
            "description": row[8] or "",
        }
        for row in cursor.fetchall()
    ]
    cursor.close()
    conn.close()

    # Filter valid candidates with an ID
    candidates = [c for c in candidates if c.get("candidate_id") is not None]

    print(f"Matching {len(candidates)} candidates against {len(jobs)} jobs...")

    # Pairwise feature matrix construction
    pairs = []
    features_list = []
    candidate_ids_list = []

    for job in jobs:
        for cand in candidates:
            sem = semantic_score(cand["raw_text"][:2000], job["description"] + " " + " ".join(job["required_skills"]))
            overlap = skill_overlap_score(cand["skills"], job["required_skills"])
            exp = experience_score(cand["experience_years"], job["required_experience"])

            pairs.append({
                "candidate": cand,
                "job": job,
                "semantic_score": float(sem),
                "skill_overlap_score": float(overlap),
                "experience_score": float(exp),
            })
            features_list.append([sem, overlap, exp])
            candidate_ids_list.append(cand["candidate_id"])

    features_arr = np.array(features_list)
    cand_ids_arr = np.array(candidate_ids_list)

    # Train or load model
    if not os.path.exists(model_path):
        print("Training ranking model...")
        labels = generate_synthetic_labels(features_arr)
        train_result = train_ranking_model(features_arr, labels, cand_ids_arr)
        save_model(train_result["model"], model_path)
        model = train_result["model"]
    else:
        print("Loading existing trained model...")
        model = load_model(model_path)

    # Inference: predict fit probability
    predictions = predict_scores(model, features_arr)

    # Build fact_applications rows with GenAI/offline insights
    applications = []
    print("Generating candidate insights and building fact rows...")
    for idx, pair in enumerate(pairs):
        cand = pair["candidate"]
        job = pair["job"]
        score = float(predictions[idx])

        # Generate insight
        insight = generate_candidate_insight(
            candidate_name=cand["name"],
            job_title=job["title"],
            job_department=job.get("department", ""),
            final_score=score,
            features={
                "semantic_score": pair["semantic_score"],
                "skill_overlap_score": pair["skill_overlap_score"],
                "experience_score": pair["experience_score"],
            },
            candidate_skills=cand["skills"],
            required_skills=job["required_skills"],
            candidate_experience=cand["experience_years"],
            required_experience=job["required_experience"],
            candidate_summary=cand.get("summary", ""),
        )

        applications.append({
            "candidate_id": cand["candidate_id"],
            "job_id": job["job_id"],
            "semantic_score": pair["semantic_score"],
            "skill_overlap_score": pair["skill_overlap_score"],
            "experience_score": pair["experience_score"],
            "final_score": score,
            "applied_date": datetime.now().date(),
            "insight_text": insight,
        })

    # Load into fact_applications
    conn = get_db_connection()
    load_fact_applications(conn, applications)
    conn.close()

    print(f"Pipeline complete! {len(applications)} matches scored and stored.")
    return len(applications)


# ---------------------------------------------------------------------------
# DAG Definition
# ---------------------------------------------------------------------------
if AIRFLOW_AVAILABLE and DAG is not None:
    with DAG(
        dag_id="resume_screening_pipeline",
        default_args=default_args,
        description="KDAC-2 End-to-End Talent Analytics & Screening Pipeline",
        schedule=None,  # Airflow 2.4+ standard for manual triggers
        catchup=False,
        tags=["talent", "screening", "nlp", "ranking"],
    ) as dag:

        t1_check_data = PythonOperator(
            task_id="check_or_generate_synthetic_data",
            python_callable=task_check_or_gen_data,
        )

        t2_parse = PythonOperator(
            task_id="parse_resumes",
            python_callable=task_parse_resumes,
        )

        t3_extract_load = PythonOperator(
            task_id="extract_entities_and_load_warehouse",
            python_callable=task_extract_and_load_dims,
        )

        t4_match_rank = PythonOperator(
            task_id="match_rank_and_load_facts",
            python_callable=task_match_rank_and_load_facts,
        )

        # Sequential execution flow
        t1_check_data >> t2_parse >> t3_extract_load >> t4_match_rank


def run_pipeline_local():
    """Execute all pipeline steps sequentially for local testing without Airflow."""
    print("Executing pipeline tasks sequentially...")
    task_check_or_gen_data()
    task_parse_resumes()
    print("[OK] Synthetic data and parsing steps complete.")


if __name__ == "__main__":
    run_pipeline_local()
