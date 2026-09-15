"""
EDA & Talent Analytics Dashboard
=================================
Streamlit application connecting to PostgreSQL data warehouse.
Visualizes:
  - Total candidates, jobs, and applications KPIs
  - Skill frequency distribution (Top 20 most prevalent skills)
  - Candidate experience level distribution (histogram & density)
  - Applications-per-job funnel / distribution
  - Average match score & top match score by job posting
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2


# Page configuration
st.set_page_config(
    page_title="KDAC-2 | Talent Analytics & EDA",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling for premium look
st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }
    .metric-card {
        background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
        border: 1px solid #374151;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }
    .metric-val {
        font-size: 2rem;
        font-weight: 700;
        color: #3b82f6;
    }
    .metric-label {
        font-size: 0.875rem;
        color: #9ca3af;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    h1, h2, h3 {
        color: #f3f4f6;
    }
</style>
""", unsafe_allow_html=True)


def get_connection():
    """Create a connection to the PostgreSQL database."""
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", 5432)),
        dbname=os.environ.get("POSTGRES_DB", "talent_analytics"),
        user=os.environ.get("POSTGRES_USER", "kdac2"),
        password=os.environ.get("POSTGRES_PASSWORD", "kdac2_dev_password"),
    )


@st.cache_data(ttl=60)
def load_eda_data():
    """Fetch aggregated datasets from PostgreSQL warehouse."""
    try:
        conn = get_connection()
    except Exception as err:
        return None, str(err)

    data = {}
    try:
        # 1. Total counts
        counts_query = """
            SELECT 
                (SELECT COUNT(*) FROM dim_candidate) AS total_candidates,
                (SELECT COUNT(*) FROM dim_job) AS total_jobs,
                (SELECT COUNT(*) FROM fact_applications) AS total_applications,
                (SELECT COUNT(*) FROM dim_skill) AS total_skills
        """
        data["counts"] = pd.read_sql_query(counts_query, conn)

        # 2. Skill frequency distribution
        skills_query = """
            SELECT s.skill_name, s.category, COUNT(b.candidate_id) AS candidate_count
            FROM dim_skill s
            LEFT JOIN bridge_candidate_skill b ON s.skill_id = b.skill_id
            GROUP BY s.skill_id, s.skill_name, s.category
            ORDER BY candidate_count DESC
            LIMIT 25
        """
        data["skills"] = pd.read_sql_query(skills_query, conn)

        # 3. Experience level distribution
        exp_query = """
            SELECT candidate_id, name, experience_years, job_family, education
            FROM dim_candidate
        """
        data["experience"] = pd.read_sql_query(exp_query, conn)

        # 4. Applications and match scores per job
        jobs_query = """
            SELECT 
                j.job_id,
                j.title,
                j.department,
                j.job_family,
                COUNT(f.application_id) AS app_count,
                ROUND(AVG(f.final_score)::numeric, 3) AS avg_final_score,
                ROUND(AVG(f.semantic_score)::numeric, 3) AS avg_semantic_score,
                ROUND(AVG(f.skill_overlap_score)::numeric, 3) AS avg_skill_overlap,
                ROUND(AVG(f.experience_score)::numeric, 3) AS avg_experience_score,
                ROUND(MAX(f.final_score)::numeric, 3) AS max_final_score
            FROM dim_job j
            LEFT JOIN fact_applications f ON j.job_id = f.job_id
            GROUP BY j.job_id, j.title, j.department, j.job_family
            ORDER BY app_count DESC, avg_final_score DESC
        """
        data["jobs"] = pd.read_sql_query(jobs_query, conn)

        conn.close()
        return data, None
    except Exception as e:
        conn.close()
        return None, str(e)


# ---------------------------------------------------------------------------
# UI Layout
# ---------------------------------------------------------------------------
st.title("🎯 KDAC-2 | Talent Analytics & EDA Dashboard")
st.caption("PostgreSQL Star Schema Analytics: Candidates, Skills, and Application Funnels")

# Refresh button in sidebar
st.sidebar.header("Controls & Filters")
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

data, error = load_eda_data()

if error:
    st.error(f"⚠️ Could not connect to PostgreSQL database: {error}")
    st.info("Ensure PostgreSQL container is running (`docker-compose up postgres`) and database is seeded.")
    st.stop()

# Top KPI Metric Cards
counts = data["counts"].iloc[0]
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-val">{int(counts['total_candidates']):,}</div>
        <div class="metric-label">Total Candidates</div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-val">{int(counts['total_jobs']):,}</div>
        <div class="metric-label">Open Job Roles</div>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-val">{int(counts['total_applications']):,}</div>
        <div class="metric-label">Evaluated Matches</div>
    </div>
    """, unsafe_allow_html=True)

with c4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-val">{int(counts['total_skills']):,}</div>
        <div class="metric-label">Tracked Skills</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# Main Visualizations: 2 Columns
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🛠️ Top 20 Candidate Skills Distribution")
    df_skills = data["skills"].head(20)
    if not df_skills.empty and df_skills["candidate_count"].sum() > 0:
        fig_skills = px.bar(
            df_skills,
            x="candidate_count",
            y="skill_name",
            orientation="h",
            color="category",
            color_discrete_map={"Technical": "#3b82f6", "Business": "#10b981"},
            labels={"candidate_count": "Candidate Count", "skill_name": "Skill", "category": "Type"},
            title="Skill Frequency Across Candidate Pool"
        )
        fig_skills.update_layout(
            yaxis={'categoryorder':'total ascending'},
            template="plotly_dark",
            height=500,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig_skills, use_container_width=True)
    else:
        st.info("No skill association records found in bridge table yet.")

with col_right:
    st.subheader("📈 Experience Level Distribution")
    df_exp = data["experience"]
    if not df_exp.empty:
        fig_exp = px.histogram(
            df_exp,
            x="experience_years",
            nbins=15,
            color="job_family",
            labels={"experience_years": "Years of Experience", "job_family": "Job Family"},
            title="Candidate Experience Histogram by Family",
            template="plotly_dark"
        )
        fig_exp.update_layout(
            bargap=0.1,
            height=500,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig_exp, use_container_width=True)
    else:
        st.info("No candidate experience data available.")

st.markdown("---")

# Row 2: Applications & Match Score Analysis by Role
col_bot_left, col_bot_right = st.columns(2)

df_jobs = data["jobs"]

with col_bot_left:
    st.subheader("📋 Applications per Job Role")
    if not df_jobs.empty:
        fig_funnel = px.bar(
            df_jobs,
            x="title",
            y="app_count",
            color="department",
            labels={"title": "Job Title", "app_count": "Application Matches"},
            title="Matches Evaluated per Posting",
            template="plotly_dark"
        )
        fig_funnel.update_layout(
            xaxis_tickangle=-45,
            height=450,
            margin=dict(l=20, r=20, t=40, b=100)
        )
        st.plotly_chart(fig_funnel, use_container_width=True)
    else:
        st.info("No job application data recorded.")

with col_bot_right:
    st.subheader("⭐ Average Match Score by Job Posting")
    if not df_jobs.empty and df_jobs["avg_final_score"].notnull().any():
        fig_scores = px.bar(
            df_jobs.sort_values(by="avg_final_score", ascending=True),
            x="avg_final_score",
            y="title",
            orientation="h",
            color="avg_final_score",
            color_continuous_scale="Blues",
            labels={"avg_final_score": "Avg Fit Score (0-1)", "title": "Job Posting"},
            title="Average ML Matching Score by Position",
            template="plotly_dark"
        )
        fig_scores.update_layout(
            height=450,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig_scores, use_container_width=True)
    else:
        st.info("Fact applications scores not populated yet. Run ML matching pipeline.")

# Detailed Data Table
with st.expander("🔍 View Raw Job Aggregations Table"):
    st.dataframe(df_jobs, use_container_width=True)
