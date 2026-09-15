"""
Recruiter Ranked Shortlist Dashboard
=====================================
Streamlit application for talent acquisition teams:
  - Select open job posting from dim_job
  - View candidates ranked by ML final_score descending
  - Displays feature breakdown: semantic_score, skill_overlap_score, experience_score
  - Displays GenAI candidate insight (Groq/offline explanation)
  - Filtering by minimum score threshold and experience
  - Export shortlist to CSV
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px
import psycopg2


st.set_page_config(
    page_title="KDAC-2 | Recruiter Shortlist",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
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
        background-color: #2563eb;
        color: white;
        padding: 4px 10px;
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
</style>
""", unsafe_allow_html=True)


def get_connection():
    """Create a PostgreSQL connection."""
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", 5432)),
        dbname=os.environ.get("POSTGRES_DB", "talent_analytics"),
        user=os.environ.get("POSTGRES_USER", "kdac2"),
        password=os.environ.get("POSTGRES_PASSWORD", "kdac2_dev_password"),
    )


@st.cache_data(ttl=60)
def load_jobs_list():
    """Fetch all open job descriptions."""
    try:
        conn = get_connection()
        query = """
            SELECT job_id, title, department, required_skills, required_experience, description
            FROM dim_job
            ORDER BY title
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)


def load_shortlist(job_id: int):
    """Fetch ranked candidate applications for a specific job."""
    try:
        conn = get_connection()
        query = """
            SELECT 
                f.application_id,
                f.final_score,
                f.semantic_score,
                f.skill_overlap_score,
                f.experience_score,
                f.insight_text,
                c.candidate_id,
                c.name AS candidate_name,
                c.email,
                c.education,
                c.university,
                c.experience_years,
                c.location,
                c.most_recent_title,
                c.resume_filename,
                ARRAY_AGG(s.skill_name) FILTER (WHERE s.skill_name IS NOT NULL) AS candidate_skills
            FROM fact_applications f
            JOIN dim_candidate c ON f.candidate_id = c.candidate_id
            LEFT JOIN bridge_candidate_skill b ON c.candidate_id = b.candidate_id
            LEFT JOIN dim_skill s ON b.skill_id = s.skill_id
            WHERE f.job_id = %s
            GROUP BY 
                f.application_id, f.final_score, f.semantic_score, 
                f.skill_overlap_score, f.experience_score, f.insight_text,
                c.candidate_id, c.name, c.email, c.education, c.university,
                c.experience_years, c.location, c.most_recent_title, c.resume_filename
            ORDER BY f.final_score DESC
        """
        df = pd.read_sql_query(query, conn, params=(job_id,))
        conn.close()
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)


# ---------------------------------------------------------------------------
# UI Layout
# ---------------------------------------------------------------------------
st.title("💼 KDAC-2 | Recruiter Shortlist & Candidate Match Engine")
st.caption("AI-Powered Ranking & Natural Language Fit Insights")

df_jobs, jobs_err = load_jobs_list()

if jobs_err:
    st.error(f"⚠️ Unable to fetch job postings: {jobs_err}")
    st.info("Check database container status.")
    st.stop()

if df_jobs.empty:
    st.warning("No job postings found in warehouse (`dim_job`). Please seed the database.")
    st.stop()

# Sidebar: Job Selector & Thresholds
st.sidebar.header("🎯 Job Filter")
job_options = {
    f"{row['title']} ({row['department']}) - ID: {row['job_id']}": row['job_id']
    for _, row in df_jobs.iterrows()
}
selected_label = st.sidebar.selectbox("Select Target Job Opening:", list(job_options.keys()))
selected_job_id = job_options[selected_label]

selected_job_meta = df_jobs[df_jobs["job_id"] == selected_job_id].iloc[0]

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Candidate Filters")
min_score = st.sidebar.slider("Minimum Fit Score (0-100%):", min_value=0, max_value=100, value=30, step=5) / 100.0
min_exp = st.sidebar.slider("Minimum Experience (Years):", min_value=0, max_value=15, value=0, step=1)
top_k = st.sidebar.number_input("Display Top K Candidates:", min_value=5, max_value=100, value=20, step=5)

# Job Overview Header
with st.expander("📌 Selected Job Description & Requirements", expanded=True):
    col_j1, col_j2 = st.columns([2, 1])
    with col_j1:
        st.subheader(selected_job_meta["title"])
        st.write(selected_job_meta["description"])
    with col_j2:
        st.write(f"**Department:** {selected_job_meta['department']}")
        st.write(f"**Required Experience:** {selected_job_meta['required_experience']} years")
        st.write("**Required Skills:**")
        if selected_job_meta["required_skills"]:
            st.write(", ".join(selected_job_meta["required_skills"]))

# Fetch and Filter Candidates
candidates_df, cand_err = load_shortlist(selected_job_id)

if cand_err:
    st.error(f"Error fetching candidate matches: {cand_err}")
    st.stop()

if candidates_df.empty:
    st.info("ℹ️ No candidate match records found for this job in `fact_applications`. Run the ML matching pipeline.")
    st.stop()

# Apply filters
filtered_df = candidates_df[
    (candidates_df["final_score"] >= min_score) &
    (candidates_df["experience_years"] >= min_exp)
].head(top_k)

st.markdown(f"### 🏆 Top Ranked Shortlist ({len(filtered_df)} candidates matched)")

# Score Distribution Mini-Chart
if not filtered_df.empty:
    fig_dist = px.histogram(
        filtered_df,
        x="final_score",
        nbins=10,
        title="Shortlist Score Distribution",
        labels={"final_score": "Final Fit Score"},
        template="plotly_dark",
        height=220
    )
    fig_dist.update_layout(margin=dict(l=20, r=20, t=30, b=20))
    st.plotly_chart(fig_dist, use_container_width=True)

# Render Shortlist
for rank, (_, cand) in enumerate(filtered_df.iterrows(), 1):
    score_pct = int(round(cand["final_score"] * 100))
    sem_pct = int(round(cand["semantic_score"] * 100))
    skill_pct = int(round(cand["skill_overlap_score"] * 100))
    exp_pct = int(round(cand["experience_score"] * 100))

    with st.container():
        st.markdown(f"""
        <div class="candidate-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="font-size: 1.25rem; font-weight: 700; color: #f8fafc;">#{rank}. {cand['candidate_name']}</span>
                    <span style="color: #94a3b8; margin-left: 8px;">— {cand['most_recent_title'] or 'Candidate'}</span>
                </div>
                <div>
                    <span class="score-badge">{score_pct}% Match</span>
                </div>
            </div>
            <div style="margin-top: 8px; color: #cbd5e1; font-size: 0.9rem;">
                📍 {cand['location'] or 'Location N/A'} &nbsp;|&nbsp; 
                🎓 {cand['education']} ({cand['university'] or 'N/A'}) &nbsp;|&nbsp; 
                ⏳ {cand['experience_years']} Years Experience &nbsp;|&nbsp;
                📄 {cand['resume_filename'] or 'File N/A'}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Candidate details inside expander
        with st.expander(f"Detailed Analytics & AI Fit Analysis for {cand['candidate_name']}"):
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Final Fit Score", f"{score_pct}%")
            m2.metric("Semantic Match", f"{sem_pct}%")
            m3.metric("Skill Overlap", f"{skill_pct}%")
            m4.metric("Experience Match", f"{exp_pct}%")

            # Skills badges
            skills_list = cand["candidate_skills"] or []
            if skills_list:
                st.markdown("**Candidate Skills:** " + " • ".join(skills_list))

            # GenAI Insight Box
            st.markdown("**💡 GenAI Talent Insight:**")
            insight = cand["insight_text"] or "No insight generated for this candidate."
            st.markdown(f'<div class="insight-box">{insight}</div>', unsafe_allow_html=True)

# Export button
if not filtered_df.empty:
    csv = filtered_df[[
        "candidate_name", "most_recent_title", "final_score",
        "semantic_score", "skill_overlap_score", "experience_score",
        "experience_years", "education", "insight_text"
    ]].to_csv(index=False).encode('utf-8')

    st.download_button(
        label="📥 Export Shortlist to CSV",
        data=csv,
        file_name=f"shortlist_job_{selected_job_id}.csv",
        mime="text/csv",
    )
