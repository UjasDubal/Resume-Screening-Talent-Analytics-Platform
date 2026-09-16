"""
=============================================================================
KDAC-2 | Intelligent Resume Screening & Talent Analytics Platform
Unified Streamlit Cloud Entry Point
=============================================================================
Deployable directly to Streamlit Community Cloud from GitHub.
Supports both live PostgreSQL (Neon / Supabase / Local) and bundled demo snapshot.
"""

import os
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="KDAC-2 | Talent Analytics & Shortlist Platform",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown("""
<style>
    .candidate-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .score-badge {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        color: white;
        padding: 6px 12px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 1.1rem;
    }
    .insight-box {
        background-color: #0f172a;
        border-left: 4px solid #38bdf8;
        padding: 12px;
        border-radius: 4px;
        margin-top: 8px;
        font-size: 0.95rem;
        color: #e2e8f0;
    }
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    .metric-val {
        font-size: 2rem;
        font-weight: 700;
        color: #38bdf8;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Database Connection & Multi-Tier Data Loader
# ---------------------------------------------------------------------------
def get_db_connection():
    """Attempt PostgreSQL connection using Streamlit secrets or environment variables."""
    import psycopg2

    # 1. Streamlit Secrets: DATABASE_URL
    if hasattr(st, "secrets") and "DATABASE_URL" in st.secrets:
        return psycopg2.connect(st.secrets["DATABASE_URL"])

    # 2. Streamlit Secrets: [postgres] block
    if hasattr(st, "secrets") and "postgres" in st.secrets:
        p = st.secrets["postgres"]
        return psycopg2.connect(
            host=p.get("host"),
            port=int(p.get("port", 5432)),
            dbname=p.get("dbname"),
            user=p.get("user"),
            password=p.get("password"),
            sslmode=p.get("sslmode", "require"),
        )

    # 3. Environment Variable: DATABASE_URL
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        return psycopg2.connect(db_url)

    # 4. Local / Docker Environment variables
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", 5432)),
        dbname=os.environ.get("POSTGRES_DB", "talent_analytics"),
        user=os.environ.get("POSTGRES_USER", "kdac2"),
        password=os.environ.get("POSTGRES_PASSWORD", "kdac2_dev_password"),
    )


@st.cache_data(ttl=300)
def load_all_data():
    """Load jobs, candidates, and applications from PostgreSQL or fallback snapshot."""
    conn = None
    data_source = "PostgreSQL"
    try:
        conn = get_db_connection()
        # Query jobs
        df_jobs = pd.read_sql_query("""
            SELECT job_id, title, department, company, location, job_family,
                   required_skills, required_experience, description
            FROM dim_job
            ORDER BY title
        """, conn)

        # Query candidates
        df_candidates = pd.read_sql_query("""
            SELECT candidate_id, name, email, education, university,
                   experience_years, location, most_recent_title, resume_filename
            FROM dim_candidate
            ORDER BY candidate_id
        """, conn)

        # Query scored applications with skills
        query_apps = """
            SELECT 
                f.application_id, f.job_id, f.candidate_id, f.final_score, f.semantic_score,
                f.skill_overlap_score, f.experience_score, f.insight_text,
                c.name AS candidate_name, c.email, c.education, c.university,
                c.experience_years, c.location, c.most_recent_title, c.resume_filename,
                ARRAY_AGG(s.skill_name) FILTER (WHERE s.skill_name IS NOT NULL) AS candidate_skills
            FROM fact_applications f
            JOIN dim_candidate c ON f.candidate_id = c.candidate_id
            LEFT JOIN bridge_candidate_skill b ON c.candidate_id = b.candidate_id
            LEFT JOIN dim_skill s ON b.skill_id = s.skill_id
            GROUP BY 
                f.application_id, f.job_id, f.candidate_id, f.final_score, f.semantic_score, 
                f.skill_overlap_score, f.experience_score, f.insight_text,
                c.candidate_id, c.name, c.email, c.education, c.university,
                c.experience_years, c.location, c.most_recent_title, c.resume_filename
            ORDER BY f.job_id, f.final_score DESC
        """
        df_apps = pd.read_sql_query(query_apps, conn)
        conn.close()
        return df_jobs, df_candidates, df_apps, "Live PostgreSQL Database"

    except Exception as err:
        # Fallback Tier 1: Bundled demo_data.json snapshot
        snapshot_path = os.path.join(os.path.dirname(__file__), "data", "demo_data.json")
        if os.path.exists(snapshot_path):
            try:
                with open(snapshot_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                df_jobs = pd.DataFrame(raw.get("jobs", []))
                df_candidates = pd.DataFrame(raw.get("candidates", []))
                df_apps = pd.DataFrame(raw.get("applications", []))
                if not df_jobs.empty:
                    return df_jobs, df_candidates, df_apps, "Bundled Snapshot (Demo Mode)"
            except Exception:
                pass

        # Fallback Tier 2: Check synthetic_jobs.json & extracted_candidates.json
        jobs_path = os.path.join(os.path.dirname(__file__), "data", "synthetic_jobs.json")
        cands_path = os.path.join(os.path.dirname(__file__), "data", "extracted_candidates.json")
        if os.path.exists(jobs_path):
            try:
                with open(jobs_path, "r", encoding="utf-8") as f:
                    raw_jobs = json.load(f)
                raw_cands = []
                if os.path.exists(cands_path):
                    with open(cands_path, "r", encoding="utf-8") as f:
                        raw_cands = json.load(f)
                df_jobs = pd.DataFrame(raw_jobs)
                df_candidates = pd.DataFrame(raw_cands)
                apps = []
                for j in raw_jobs[:6]:
                    for c in raw_cands[:15]:
                        apps.append({
                            "application_id": len(apps) + 1,
                            "job_id": j.get("job_id", 1),
                            "candidate_id": c.get("candidate_id", 1),
                            "final_score": 0.58,
                            "semantic_score": 0.62,
                            "skill_overlap_score": 0.55,
                            "experience_score": 1.0,
                            "candidate_name": c.get("name", "Candidate"),
                            "education": c.get("education", "B.Tech CSE"),
                            "experience_years": float(c.get("experience_years", 0.0) or 0.0),
                            "most_recent_title": c.get("most_recent_title", "Student Developer"),
                            "candidate_skills": c.get("skills", ["Python", "SQL", "Docker"]),
                            "insight_text": f"Candidate demonstrates strong technical alignment for {j.get('title')}."
                        })
                return df_jobs, df_candidates, pd.DataFrame(apps), "Synthetic Dataset (Demo Mode)"
            except Exception:
                pass

        # Fallback Tier 3: In-Memory Production Sample (Guarantees zero crashes anywhere)
        default_jobs = [
            {"job_id": 1, "title": "Machine Learning Engineer", "department": "Data Science", "company": "KDAC Tech", "location": "Remote", "job_family": "Data", "required_skills": ["Python", "TensorFlow", "SQL", "Docker", "Git"], "required_experience": 0, "description": "Design feature pipelines, train deep learning models, and monitor production inference performance."},
            {"job_id": 2, "title": "Full Stack Developer", "department": "Engineering", "company": "KDAC Tech", "location": "Hybrid", "job_family": "Software", "required_skills": ["React", "Node.js", "JavaScript", "SQL", "Git"], "required_experience": 1, "description": "Develop modern user interfaces and robust microservice APIs with React and Node.js."},
            {"job_id": 3, "title": "Data Analyst", "department": "Analytics", "company": "KDAC Tech", "location": "Bangalore", "job_family": "Data", "required_skills": ["SQL", "Python", "Tableau", "Excel", "Statistics"], "required_experience": 0, "description": "Analyze operational metrics, generate executive dashboards, and extract business intelligence insights."},
            {"job_id": 4, "title": "DevOps Engineer", "department": "Infrastructure", "company": "KDAC Tech", "location": "Remote", "job_family": "DevOps", "required_skills": ["Docker", "Kubernetes", "Linux", "AWS", "CI/CD"], "required_experience": 1, "description": "Maintain cloud infrastructure, automate deployment pipelines, and optimize containerized workloads."},
        ]
        default_candidates = [
            {"candidate_id": 1, "name": "Vraj Amin", "most_recent_title": "AI/ML Enthusiast", "education": "B.Tech Computer Science Engineering", "university": "Faculty of Technology", "experience_years": 1.0, "location": "Ahmedabad", "resume_filename": "Vraj_Amin_Resume.pdf"},
            {"candidate_id": 2, "name": "Amulya Anamdasu", "most_recent_title": "Aspiring Data Analyst", "education": "B.Tech Computer Science Engineering", "university": "Faculty of Technology", "experience_years": 0.0, "location": "Ahmedabad", "resume_filename": "Amulya_Anamdasu_Resume.pdf"},
            {"candidate_id": 3, "name": "Aryan Chauhan", "most_recent_title": "Frontend Developer", "education": "B.Tech Computer Science Engineering", "university": "Faculty of Technology", "experience_years": 1.0, "location": "Ahmedabad", "resume_filename": "Aryan_Chauhan_Resume.pdf"},
            {"candidate_id": 4, "name": "Krinna Anandpara", "most_recent_title": "Computer Science Student / Aspiring Engineer", "education": "B.Tech Computer Science Engineering", "university": "Faculty of Technology", "experience_years": 0.0, "location": "Ahmedabad", "resume_filename": "Krinna_Anandpara_Resume.pdf"},
            {"candidate_id": 5, "name": "Devasya Gupta", "most_recent_title": "Software Engineering Intern", "education": "B.Tech Computer Science Engineering", "university": "Faculty of Technology", "experience_years": 0.0, "location": "Ahmedabad", "resume_filename": "Devasya_Gupta_Resume.pdf"},
        ]
        default_apps = [
            {"application_id": 1, "job_id": 1, "candidate_id": 1, "final_score": 0.85, "semantic_score": 0.82, "skill_overlap_score": 0.80, "experience_score": 1.0, "candidate_name": "Vraj Amin", "most_recent_title": "AI/ML Enthusiast", "education": "B.Tech CSE", "experience_years": 1.0, "resume_filename": "Vraj_Amin_Resume.pdf", "candidate_skills": ["Python", "TensorFlow", "Docker", "SQL", "Git"], "insight_text": "Vraj Amin is an outstanding match for Machine Learning Engineer, possessing direct hands-on experience in Python, TensorFlow, and Docker with high semantic alignment."},
            {"application_id": 2, "job_id": 1, "candidate_id": 2, "final_score": 0.62, "semantic_score": 0.65, "skill_overlap_score": 0.50, "experience_score": 1.0, "candidate_name": "Amulya Anamdasu", "most_recent_title": "Aspiring Data Analyst", "education": "B.Tech CSE", "experience_years": 0.0, "resume_filename": "Amulya_Anamdasu_Resume.pdf", "candidate_skills": ["Python", "SQL", "Tableau", "Excel"], "insight_text": "Solid technical foundation in Python and SQL with strong analytical and problem solving capabilities."},
            {"application_id": 3, "job_id": 2, "candidate_id": 3, "final_score": 0.88, "semantic_score": 0.86, "skill_overlap_score": 0.85, "experience_score": 1.0, "candidate_name": "Aryan Chauhan", "most_recent_title": "Frontend Developer", "education": "B.Tech CSE", "experience_years": 1.0, "resume_filename": "Aryan_Chauhan_Resume.pdf", "candidate_skills": ["React", "JavaScript", "Node.js", "Git", "HTML", "CSS"], "insight_text": "Strong fit for Full Stack Developer with practical React and Node.js project experience and collaborative Git workflows."},
            {"application_id": 4, "job_id": 1, "candidate_id": 5, "final_score": 0.72, "semantic_score": 0.70, "skill_overlap_score": 0.65, "experience_score": 1.0, "candidate_name": "Devasya Gupta", "most_recent_title": "Software Engineering Intern", "education": "B.Tech CSE", "experience_years": 0.0, "resume_filename": "Devasya_Gupta_Resume.pdf", "candidate_skills": ["Python", "SQL", "Docker", "Git", "C++"], "insight_text": "Promising software engineering background with good fundamentals in containerization and relational databases."},
            {"application_id": 5, "job_id": 3, "candidate_id": 2, "final_score": 0.84, "semantic_score": 0.80, "skill_overlap_score": 0.85, "experience_score": 1.0, "candidate_name": "Amulya Anamdasu", "most_recent_title": "Aspiring Data Analyst", "education": "B.Tech CSE", "experience_years": 0.0, "resume_filename": "Amulya_Anamdasu_Resume.pdf", "candidate_skills": ["Python", "SQL", "Tableau", "Excel", "Statistics"], "insight_text": "Excellent match for Data Analyst role with direct competence in SQL, Tableau dashboarding, and exploratory data analysis."},
        ]
        return pd.DataFrame(default_jobs), pd.DataFrame(default_candidates), pd.DataFrame(default_apps), "Demo / Preview Mode"


# ---------------------------------------------------------------------------
# Sidebar & Navigation
# ---------------------------------------------------------------------------
df_jobs, df_candidates, df_apps, data_source = load_all_data()

st.sidebar.title("💼 KDAC-2 Platform")
st.sidebar.caption(f"Data Source: **{data_source}**")

nav = st.sidebar.radio(
    "Select View / Module:",
    ["💼 Recruiter Shortlist & Match Engine", "📊 EDA & Talent Analytics", "ℹ️ System Architecture"],
    index=0
)

# ---------------------------------------------------------------------------
# View 1: Recruiter Shortlist & Match Engine
# ---------------------------------------------------------------------------
if nav == "💼 Recruiter Shortlist & Match Engine":
    st.title("💼 Recruiter Shortlist & Candidate Match Engine")
    st.caption("AI-Powered Candidate Ranking, Skill Overlap & Natural Language Fit Insights")

    if df_jobs.empty:
        st.warning("⚠️ No job postings found. Please check your database connection.")
        st.stop()

    job_options = {
        f"{row['title']} ({row['department']})": row['job_id']
        for _, row in df_jobs.iterrows()
    }

    col_select, col_meta = st.columns([1, 2])
    with col_select:
        selected_label = st.selectbox("🎯 Select Target Job Opening:", list(job_options.keys()))
        selected_job_id = job_options[selected_label]

    selected_job_meta = df_jobs[df_jobs["job_id"] == selected_job_id].iloc[0]

    with st.expander("📌 Selected Job Description & Requirements", expanded=True):
        col_j1, col_j2 = st.columns([2, 1])
        with col_j1:
            st.subheader(selected_job_meta["title"])
            st.write(selected_job_meta.get("description", "No description provided."))
        with col_j2:
            st.write(f"**Department:** {selected_job_meta.get('department', 'N/A')}")
            st.write(f"**Required Experience:** {selected_job_meta.get('required_experience', 0)} years")
            req_skills = selected_job_meta.get("required_skills", [])
            if req_skills:
                st.write("**Required Skills:**")
                st.write(", ".join(req_skills))

    # Filters
    st.sidebar.markdown("---")
    st.sidebar.header("⚙️ Candidate Filters")
    min_score = st.sidebar.slider("Minimum Fit Score (%):", 0, 100, 30, step=5) / 100.0
    min_exp = st.sidebar.slider("Minimum Experience (Years):", 0, 15, 0, step=1)
    top_k = st.sidebar.number_input("Display Top K Candidates:", 5, 100, 20, step=5)

    # Filter candidates for this job
    job_apps = df_apps[df_apps["job_id"] == selected_job_id] if not df_apps.empty else pd.DataFrame()

    if job_apps.empty:
        st.info("ℹ️ No candidate match records found for this job. Run the ML matching pipeline.")
        st.stop()

    filtered_df = job_apps[
        (job_apps["final_score"] >= min_score) &
        (job_apps["experience_years"] >= min_exp)
    ].head(top_k)

    # Metrics Summary Row
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Applicants Evaluated", len(job_apps))
    m2.metric("Candidates Meeting Threshold", len(filtered_df))
    avg_score = round(job_apps["final_score"].mean() * 100, 1) if not job_apps.empty else 0
    m3.metric("Average Role Fit", f"{avg_score}%")
    top_score = round(job_apps["final_score"].max() * 100, 1) if not job_apps.empty else 0
    m4.metric("Top Candidate Fit", f"{top_score}%")

    # Fit Score Distribution
    with st.expander("📊 Fit Score Distribution for this Position", expanded=False):
        fig_dist = px.histogram(
            job_apps,
            x="final_score",
            nbins=20,
            color_discrete_sequence=["#38bdf8"],
            labels={"final_score": "Final Fit Score"},
            template="plotly_dark",
            height=240
        )
        fig_dist.update_layout(margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_dist, use_container_width=True)

    # Render Shortlist Cards
    st.subheader(f"🏆 Top {len(filtered_df)} Recommended Candidates")

    for rank, (_, cand) in enumerate(filtered_df.iterrows(), 1):
        score_pct = int(round(cand["final_score"] * 100))
        sem_pct = int(round(cand["semantic_score"] * 100))
        skill_pct = int(round(cand["skill_overlap_score"] * 100))
        exp_pct = int(round(cand["experience_score"] * 100))

        st.markdown(f"""
        <div class="candidate-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="font-size: 1.25rem; font-weight: 700; color: #f8fafc;">#{rank}. {cand['candidate_name']}</span>
                    <span style="color: #94a3b8; margin-left: 8px;">— {cand.get('most_recent_title') or 'Candidate'}</span>
                </div>
                <div>
                    <span class="score-badge">{score_pct}% Match</span>
                </div>
            </div>
            <div style="margin-top: 8px; color: #cbd5e1; font-size: 0.9rem;">
                🎓 {cand.get('education', 'N/A')} &nbsp;|&nbsp; 
                ⏳ {cand.get('experience_years', 0):.0f} Years Experience &nbsp;|&nbsp;
                📄 {cand.get('resume_filename') or 'Document'}
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.expander(f"Detailed Analytics & AI Fit Analysis for {cand['candidate_name']}"):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Final Fit Score", f"{score_pct}%")
            c2.metric("Semantic Match", f"{sem_pct}%")
            c3.metric("Skill Overlap", f"{skill_pct}%")
            c4.metric("Experience Match", f"{exp_pct}%")

            skills = cand.get("candidate_skills") or []
            if skills:
                st.markdown("**Identified Skills:** " + " • ".join(skills))

            st.markdown("**💡 GenAI Talent Insight:**")
            insight = cand.get("insight_text") or "Candidate evaluated by ranking model."
            st.markdown(f'<div class="insight-box">{insight}</div>', unsafe_allow_html=True)

    # Export Button
    if not filtered_df.empty:
        csv = filtered_df[[
            "candidate_name", "most_recent_title", "final_score",
            "semantic_score", "skill_overlap_score", "experience_score",
            "experience_years", "education", "insight_text"
        ]].to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export Candidate Shortlist to CSV",
            data=csv,
            file_name=f"shortlist_job_{selected_job_id}.csv",
            mime="text/csv",
        )

# ---------------------------------------------------------------------------
# View 2: EDA & Talent Analytics Dashboard
# ---------------------------------------------------------------------------
elif nav == "📊 EDA & Talent Analytics":
    st.title("📊 Talent Analytics & Pipeline Intelligence")
    st.caption("Star Schema Warehouse Metrics, Skill Frequencies & Cross-Role Compatibility")

    # High-level Metrics Row
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-val">{len(df_candidates)}</div>
            <div class="metric-label">Total Candidates</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-val">{len(df_jobs)}</div>
            <div class="metric-label">Open Job Postings</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-val">{len(df_apps)}</div>
            <div class="metric-label">Total Matches Scored</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        avg_exp = round(df_candidates["experience_years"].mean(), 1) if not df_candidates.empty else 0
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-val">{avg_exp} yrs</div>
            <div class="metric-label">Avg Experience</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.subheader("🎯 Overall Fit Score Distribution")
        if not df_apps.empty:
            fig_hist = px.histogram(
                df_apps,
                x="final_score",
                nbins=25,
                color_discrete_sequence=["#2563eb"],
                labels={"final_score": "Model Predicted Fit Score"},
                template="plotly_dark",
            )
            st.plotly_chart(fig_hist, use_container_width=True)

    with col_chart2:
        st.subheader("🏢 Open Positions by Department")
        if not df_jobs.empty:
            dept_counts = df_jobs["department"].value_counts().reset_index()
            dept_counts.columns = ["Department", "Job Count"]
            fig_pie = px.pie(
                dept_counts,
                names="Department",
                values="Job Count",
                color_discrete_sequence=px.colors.sequential.Blues_r,
                template="plotly_dark",
                hole=0.4
            )
            st.plotly_chart(fig_pie, use_container_width=True)

    # Top Candidate Skills Analysis
    st.subheader("🛠️ Most Prevalent Skills in Candidate Pool")
    if not df_apps.empty:
        all_skills = []
        for s_list in df_apps["candidate_skills"].dropna():
            if isinstance(s_list, list):
                all_skills.extend(s_list)
        if all_skills:
            skill_counts = pd.Series(all_skills).value_counts().head(15).reset_index()
            skill_counts.columns = ["Skill", "Count"]
            fig_skills = px.bar(
                skill_counts,
                x="Count",
                y="Skill",
                orientation="h",
                color="Count",
                color_continuous_scale="Blues",
                template="plotly_dark",
            )
            fig_skills.update_layout(yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig_skills, use_container_width=True)

# ---------------------------------------------------------------------------
# View 3: System Architecture & Deployment Info
# ---------------------------------------------------------------------------
else:
    st.title("ℹ️ System Architecture & Deployment")
    st.markdown("""
    ### 🏗️ Enterprise Talent Intelligence Pipeline

    This platform orchestrates end-to-end resume ingestion, entity extraction, data warehousing, and AI-powered ranking.

    ```
    [Raw Resumes PDF/DOCX] ──► [Apache Airflow Ingestion] ──► [spaCy NER & Parser]
                                                                      │
                                                                      ▼
    [Streamlit Cloud UI]  ◄── [PostgreSQL Star Schema]  ◄── [ML Ranking & Groq GenAI]
    ```

    #### ✨ Key Components:
    * **Data Warehouse**: PostgreSQL Star Schema with `dim_candidate`, `dim_job`, `dim_skill`, and `fact_applications`.
    * **Feature Engineering**: Cosine similarity on 384-dimensional SentenceTransformer embeddings (`all-MiniLM-L6-v2`), Jaccard skill overlap, and normalized experience matching.
    * **Machine Learning**: Logistic Regression ranking model trained with `GroupShuffleSplit` grouping by candidate to guarantee zero data leakage.
    * **GenAI**: Groq API integration (Llama 3 / Qwen) producing concise, actionable fit evaluations and gap analysis.

    #### 🌐 Connecting a Live Cloud Database:
    To connect this app to a free PostgreSQL database (e.g. [Neon.tech](https://neon.tech) or [Supabase](https://supabase.com)):
    1. Create a free PostgreSQL instance on **Neon** or **Supabase**.
    2. In your **Streamlit Community Cloud** App settings, navigate to **Secrets**.
    3. Add:
       ```toml
       DATABASE_URL = "postgresql://user:password@ep-xyz.neon.tech/neondb?sslmode=require"
       GROQ_API_KEY = "gsk_your_groq_key"
       ```
    4. Save — Streamlit Cloud will instantly switch from Demo mode to your live cloud database!
    """)
