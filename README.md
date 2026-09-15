# KDAC-2 Resume Screening & Talent Analytics Platform

A complete, production-grade, locally-runnable **Resume Screening & Talent Analytics Platform** orchestrating synthetic data generation, multimodal resume parsing, PostgreSQL star schema data warehousing, machine learning candidate-to-job matching, Groq GenAI insights (with offline fallback), two Streamlit dashboards, and Apache Airflow orchestration.

---

## 🏗️ System Architecture

```
                               ┌────────────────────────────────┐
                               │  Synthetic Data Generator     │
                               │  - 200 PDFs/DOCX Resumes       │
                               │  - 18 Job Descriptions (JSON)  │
                               └───────────────┬────────────────┘
                                               │
                                               ▼
                               ┌────────────────────────────────┐
                               │       ETL & Parsing            │
                               │  - pdfplumber + PyMuPDF        │
                               │  - python-docx                 │
                               │  - spaCy NER + PhraseMatcher   │
                               └───────────────┬────────────────┘
                                               │
                                               ▼
                               ┌────────────────────────────────┐
                               │ PostgreSQL Data Warehouse      │
                               │ (Star Schema + Bridge Table)   │
                               │ - dim_candidate, dim_job       │
                               │ - dim_skill, bridge_cand_skill │
                               │ - dim_company, dim_time        │
                               │ - fact_applications            │
                               └───────┬────────────────┬───────┘
                                       │                │
            ┌──────────────────────────┘                └──────────────────────────┐
            ▼                                                                      ▼
┌───────────────────────────────┐                                  ┌───────────────────────────────┐
│     ML Matching & Ranking     │                                  │   GenAI Talent Insights       │
│ - sentence-transformers       │                                  │ - Groq API (Llama 3.3 70B)    │
│   (all-MiniLM-L6-v2)          │                                  │ - Deterministic Offline       │
│ - LogisticRegression ranking  │                                  │   Fallback Template           │
│ - GroupShuffleSplit (no leak) │                                  └───────────────┬───────────────┘
└───────────────┬───────────────┘                                                  │
                │                                                                  │
                └──────────────────────────────┬───────────────────────────────────┘
                                               │
                                               ▼
                         ┌───────────────────────────────────────────┐
                         │              Streamlit Dashboards         │
                         │  - EDA & Analytics (Port 8501)            │
                         │  - Recruiter Shortlist Engine (Port 8502) │
                         │  - Airflow Standalone UI (Port 8080)      │
                         └───────────────────────────────────────────┘
```

---

## 🚀 Quickstart & Setup

### 1. Prerequisites
- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/)
- At least 6–8 GB RAM allocated to Docker Desktop

### 2. Configure Environment
Clone the repository and copy the environment template:
```bash
cp .env.example .env
```

Review or edit `.env` if desired:
```ini
POSTGRES_USER=kdac2
POSTGRES_PASSWORD=kdac2_dev_password
POSTGRES_DB=talent_analytics
POSTGRES_PORT=5432

MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123
MINIO_PORT=9000
MINIO_CONSOLE_PORT=9001

# Optional: Add your Groq API key for real-time LLM explanations.
# If left blank, the platform seamlessly uses deterministic offline insights.
GROQ_API_KEY=

STREAMLIT_EDA_PORT=8501
STREAMLIT_RECRUITER_PORT=8502
AIRFLOW_PORT=8080
```

### 3. Launch via Docker Compose
Run the entire platform with a single command:
```bash
docker-compose up --build
```

All 5 core services will launch with built-in health checks:
1. `kdac2-postgres` (Port 5432)
2. `kdac2-minio` (Port 9000 API, 9001 Console)
3. `kdac2-airflow` (Port 8080)
4. `kdac2-eda-dashboard` (Port 8501)
5. `kdac2-recruiter-dashboard` (Port 8502)

---

## 🌐 Dashboard & Interface Access Points

| Service | URL | Description | Credentials |
|---|---|---|---|
| **EDA Dashboard** | [http://localhost:8501](http://localhost:8501) | Skill frequencies, experience distribution, and match funnels | None |
| **Recruiter Shortlist** | [http://localhost:8502](http://localhost:8502) | AI-ranked shortlist per job, feature breakdown & GenAI insights | None |
| **Airflow Orchestrator** | [http://localhost:8080](http://localhost:8080) | Standalone Airflow DAG monitor and pipeline trigger | Logged in container logs |
| **MinIO Console** | [http://localhost:9001](http://localhost:9001) | Object storage web console for raw resumes | `minioadmin` / `minioadmin123` |

---

## 🧪 Local CLI Development & Testing

You can also run individual modules directly without Docker:

```bash
# 1. Install dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# 2. Generate synthetic data
python synth/generate_jobs.py
python synth/generate_resumes.py

# 3. Run Parser & Entity Extraction
python etl/parser.py
python etl/ner_extract.py

# 4. Train Ranking Model & Evaluate
python ml/train_ranking_model.py

# 5. Run Automated Test Suite
pytest tests/ -v
```

---

## 🏛️ Star Schema Architecture (`db/schema.sql`)

The PostgreSQL data warehouse implements a high-performance **Star Schema** optimized for talent analytics:
- **`dim_candidate`**: Stores candidate demographic information, contact data, education, total years of experience, and source resume filename.
- **`dim_job`**: Stores open position details, hiring department, required qualifications, required experience, and role descriptions.
- **`dim_skill`**: Normalized registry of tech and business skills categorized into `Technical` and `Business`.
- **`bridge_candidate_skill`**: High-performance junction table mapping candidate IDs to skill IDs, enabling fast set-overlap queries and skill frequency aggregations.
- **`dim_company`**: Unique company records extracted from candidate employment history.
- **`dim_time`**: Date dimension representing application timestamps (pre-populated across date intervals).
- **`fact_applications`**: Central fact table storing calculated candidate-job match metrics: `semantic_score`, `skill_overlap_score`, `experience_score`, model-predicted `final_score`, application date foreign key, and generated natural-language `insight_text`.

---

## 🧠 ML Ranking Model & Labeling Methodology

### Labeling Assumption (Simulated Proxy Label)
> **Academic / Viva Note:** Because real proprietary hiring outcomes are unavailable and PII-sensitive, the ranking model is trained on a **simulated proxy ground-truth label**. A candidate-job pair is initially assigned `fit = 1` if `skill_overlap_score >= 0.5` AND `experience_score >= 0.6`, else `0`. Subsequently, **10% of labels are randomly flipped** to introduce realistic real-world noise, imperfect recruiter decisions, and unobserved hiring variance. This proxy rule is documented explicitly in code and should not be confused with live production hiring data.

### Train/Test Split Strategy (GroupShuffleSplit)
To prevent subtle data leakage, the model enforces `GroupShuffleSplit` grouped strictly by `candidate_id`. This guarantees that **no candidate appears in both the training set and the evaluation set**. An explicit assertion checks this in code during training (`assert len(train_ids & test_ids) == 0`).

### Feature Breakdown
1. **`semantic_score`**: Cosine similarity between 384-dimensional text embeddings of the resume and job posting using HuggingFace's `sentence-transformers/all-MiniLM-L6-v2`.
2. **`skill_overlap_score`**: Jaccard similarity ($|A \cap B| / |A \cup B|$) comparing candidate skills extracted by spaCy PhraseMatcher against the job's required skills.
3. **`experience_score`**: Normalized deviation between candidate experience and job required experience ($1 - |years_{cand} - years_{req}| / \max(years_{req}, 1)$).

### Inference
During scoring, hardcoded weights are replaced by the trained `LogisticRegression.predict_proba()` output to yield calibrated, probability-based `final_score` values.

---

## 🤖 GenAI Insights & Offline Fallback

The platform integrates Groq's fast LPU cloud inference using Meta's `llama-3.3-70b-versatile` (with automatic fallback to `llama-3.1-8b-instant`). It synthesizes a concise 3-sentence profile:
- 2 sentences highlighting alignment with the role based on key skill and experience overlap.
- 1 actionable sentence identifying specific development gaps or experience differentials.

**Zero-Dependency Guarantee:** If `GROQ_API_KEY` is not provided or network calls fail, `genai/insight_generator.py` seamlessly produces a deterministic, template-driven breakdown based on exact score calculations without crashing or interrupting the pipeline.

---

## 📦 Project Directory Layout

```
kdac2-resume-platform/
├── docker-compose.yml           # Multi-container service definitions
├── Dockerfile                   # Unified container image with dependencies & spaCy models
├── .env.example                 # Committed environment variable template
├── .env                         # Local environment configuration (gitignored)
├── .gitignore                   # Git exclusion rules
├── README.md                    # Project documentation & architecture brief
├── requirements.txt             # Pinned library requirements
├── pytest.ini                   # Pytest test suite configuration
├── data/
│   ├── raw_resumes/             # Synthetic PDF & DOCX resumes
│   └── synthetic_jobs.json      # Synthetic job description library
├── db/
│   └── schema.sql               # Star schema DDL with auto-init
├── synth/
│   ├── generate_resumes.py      # Faker + reportlab + python-docx resume generator
│   └── generate_jobs.py         # Job posting generator across 5 career families
├── etl/
│   ├── parser.py                # pdfplumber + PyMuPDF fallback + docx parser
│   ├── ner_extract.py           # spaCy NER + PhraseMatcher skill extractor
│   └── load_warehouse.py        # PostgreSQL warehouse ingestion module
├── ml/
│   ├── embeddings.py            # all-MiniLM-L6-v2 sentence embedding wrapper
│   ├── features.py              # Semantic, Jaccard skill, and experience features
│   ├── train_ranking_model.py   # GroupShuffleSplit + LogisticRegression ranking
│   └── model.pkl                # Serialized model artifact
├── genai/
│   └── insight_generator.py     # Groq chat completion + offline fallback engine
├── dashboards/
│   ├── eda_dashboard.py         # Streamlit Talent Analytics EDA application
│   └── recruiter_dashboard.py   # Streamlit Recruiter Ranked Shortlist application
├── airflow/
│   └── dags/
│       └── pipeline_dag.py      # End-to-end Airflow pipeline DAG
└── tests/
    ├── conftest.py              # Pytest system path configuration
    ├── test_parser.py           # PDF fallback & DOCX parsing tests
    ├── test_features.py         # Score calculation & bounds tests
    └── test_ranking_model.py    # Leakage prevention & serialization tests
```

---

## 🛡️ Verification & Test Suite

Run unit and integration tests:
```bash
pytest tests/ -v
```
All tests verify:
- Fallback from `pdfplumber` to `PyMuPDF` when extracted word count is `<20`.
- Extraction of tables and paragraphs from Word documents (`.docx`).
- Score bounds and edge cases for Jaccard skill similarity and experience differences.
- Zero candidate ID leakage between training and testing splits.
