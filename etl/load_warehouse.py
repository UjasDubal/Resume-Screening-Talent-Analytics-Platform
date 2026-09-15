"""
Warehouse Loader
==================
Loads parsed and extracted resume data into the PostgreSQL star schema.

Handles:
  - dim_candidate: candidate profiles
  - dim_skill: unique skills
  - bridge_candidate_skill: candidate-skill associations
  - dim_job: job descriptions (from synthetic_jobs.json)
  - dim_company: companies from work history
  - fact_applications: match scores (populated after ML scoring)
"""

import os
import json
from datetime import date, datetime
from typing import Optional

import psycopg2
from psycopg2.extras import execute_values


def get_db_connection():
    """Create a PostgreSQL connection using environment variables."""
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", 5432)),
        dbname=os.environ.get("POSTGRES_DB", "talent_analytics"),
        user=os.environ.get("POSTGRES_USER", "kdac2"),
        password=os.environ.get("POSTGRES_PASSWORD", "kdac2_dev_password"),
    )


def load_skills(conn, skills_list: list) -> dict:
    """
    Load unique skills into dim_skill and return a mapping of skill_name -> skill_id.
    """
    cursor = conn.cursor()

    # Categorize skills (simple heuristic)
    tech_skills = {
        "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Go", "Rust",
        "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R", "SQL",
        "React", "Angular", "Vue.js", "Node.js", "Django", "Flask", "FastAPI",
        "Spring Boot", "Docker", "Kubernetes", "Terraform", "AWS", "Azure", "GCP",
        "PostgreSQL", "MySQL", "MongoDB", "Redis", "Git", "CI/CD", "Linux",
        "REST APIs", "GraphQL", "Microservices", "Pandas", "NumPy", "Scikit-learn",
        "TensorFlow", "PyTorch", "Spark", "Hadoop", "Airflow", "HTML", "CSS",
        "Jenkins", "GitHub Actions",
    }

    for skill_name in set(skills_list):
        category = "Technical" if skill_name in tech_skills else "Business"
        cursor.execute(
            """
            INSERT INTO dim_skill (skill_name, category)
            VALUES (%s, %s)
            ON CONFLICT (skill_name) DO NOTHING
            """,
            (skill_name, category)
        )

    conn.commit()

    # Fetch mapping
    cursor.execute("SELECT skill_id, skill_name FROM dim_skill")
    skill_map = {row[1]: row[0] for row in cursor.fetchall()}
    cursor.close()
    return skill_map


def load_candidates(conn, candidates: list, skill_map: dict) -> dict:
    """
    Load candidates into dim_candidate and bridge_candidate_skill.
    Returns mapping of source_file -> candidate_id.
    """
    cursor = conn.cursor()
    file_to_id = {}

    for candidate in candidates:
        cursor.execute(
            """
            INSERT INTO dim_candidate
                (name, email, education, university, experience_years,
                 location, most_recent_title, job_family, resume_filename)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING candidate_id
            """,
            (
                candidate.get("name", "Unknown"),
                candidate.get("email", ""),
                candidate.get("education", "Not specified"),
                candidate.get("university", ""),
                candidate.get("experience_years", 0),
                candidate.get("location", ""),
                candidate.get("most_recent_title", ""),
                candidate.get("job_family", ""),
                candidate.get("source_file", ""),
            )
        )
        candidate_id = cursor.fetchone()[0]
        file_to_id[candidate.get("source_file", "")] = candidate_id

        # Insert candidate-skill associations
        for skill_name in candidate.get("skills", []):
            skill_id = skill_map.get(skill_name)
            if skill_id:
                cursor.execute(
                    """
                    INSERT INTO bridge_candidate_skill (candidate_id, skill_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (candidate_id, skill_id)
                )

    conn.commit()
    cursor.close()
    return file_to_id


def load_jobs(conn, jobs_path: str) -> list:
    """Load job descriptions from JSON into dim_job."""
    with open(jobs_path, "r") as f:
        jobs = json.load(f)

    cursor = conn.cursor()
    job_ids = []

    for job in jobs:
        cursor.execute(
            """
            INSERT INTO dim_job
                (title, department, company, location, job_family,
                 required_skills, required_experience, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING job_id
            """,
            (
                job["title"],
                job["department"],
                job.get("company", ""),
                job.get("location", ""),
                job.get("job_family", ""),
                job["required_skills"],
                job["required_experience"],
                job.get("description", ""),
            )
        )
        job_id = cursor.fetchone()[0]
        job_ids.append(job_id)

    conn.commit()
    cursor.close()
    print(f"[OK] Loaded {len(job_ids)} jobs into dim_job")
    return job_ids


def load_companies(conn, candidates: list):
    """Extract and load unique companies from work histories."""
    cursor = conn.cursor()
    seen = set()

    for candidate in candidates:
        for job in candidate.get("work_experience", []):
            company_name = job.get("company", "")
            industry = job.get("industry", "")
            if company_name and company_name not in seen:
                seen.add(company_name)
                cursor.execute(
                    """
                    INSERT INTO dim_company (name, industry)
                    VALUES (%s, %s)
                    """,
                    (company_name, industry)
                )

    conn.commit()
    cursor.close()
    print(f"[OK] Loaded {len(seen)} companies into dim_company")


def load_fact_applications(conn, applications: list):
    """
    Load match scores into fact_applications.

    Each application dict should have:
        candidate_id, job_id, semantic_score, skill_overlap_score,
        experience_score, final_score, applied_date, insight_text
    """
    cursor = conn.cursor()

    for app in applications:
        # Get or create date_id
        applied_date = app.get("applied_date", date.today())
        if isinstance(applied_date, str):
            applied_date = datetime.strptime(applied_date, "%Y-%m-%d").date()

        cursor.execute(
            "SELECT date_id FROM dim_time WHERE full_date = %s",
            (applied_date,)
        )
        row = cursor.fetchone()
        if row:
            date_id = row[0]
        else:
            # Insert a new date if not in dim_time
            cursor.execute(
                """
                INSERT INTO dim_time (full_date, day, month, quarter, year)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING date_id
                """,
                (
                    applied_date,
                    applied_date.day,
                    applied_date.month,
                    (applied_date.month - 1) // 3 + 1,
                    applied_date.year,
                )
            )
            date_id = cursor.fetchone()[0]

        cursor.execute(
            """
            INSERT INTO fact_applications
                (candidate_id, job_id, date_id, semantic_score,
                 skill_overlap_score, experience_score, final_score,
                 applied_date, insight_text)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                app["candidate_id"],
                app["job_id"],
                date_id,
                app["semantic_score"],
                app["skill_overlap_score"],
                app["experience_score"],
                app["final_score"],
                applied_date,
                app.get("insight_text", ""),
            )
        )

    conn.commit()
    cursor.close()
    print(f"[OK] Loaded {len(applications)} fact_applications records")


def clear_all_data(conn):
    """Clear all data from all tables (useful for re-runs)."""
    cursor = conn.cursor()
    tables = [
        "fact_applications",
        "bridge_candidate_skill",
        "dim_candidate",
        "dim_job",
        "dim_company",
        "dim_skill",
    ]
    for table in tables:
        cursor.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
    conn.commit()
    cursor.close()
    print("[OK] Cleared all data from warehouse tables")


if __name__ == "__main__":
    conn = get_db_connection()
    print("Connected to PostgreSQL")

    # Test connection
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM dim_time")
    count = cursor.fetchone()[0]
    print(f"  dim_time has {count} rows")
    cursor.close()

    conn.close()
