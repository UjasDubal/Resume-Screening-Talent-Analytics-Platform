"""
NER & Skill Extraction
=======================
Uses a hybrid approach combining filename cleaning, header text heuristics,
spaCy NER, and curated PhraseMatcher dictionaries to accurately extract structured
candidate information from resume text.

Output format:
  {
      "name": str,
      "skills": [str, ...],
      "education": str,
      "experience_years": float,
      "most_recent_title": str
  }
"""

import os
import re
import spacy
from spacy.matcher import PhraseMatcher


# ---------------------------------------------------------------------------
# Curated Skills List (~110 skills across tech, data science, and business)
# ---------------------------------------------------------------------------
SKILLS_LIST = [
    # Programming Languages
    "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "C", "Go", "Rust",
    "Ruby", "PHP", "Swift", "Kotlin", "Dart", "Scala", "R", "SQL", "Bash", "Shell",
    # Web Frameworks & Frontend
    "React", "Angular", "Vue.js", "Node.js", "Django", "Flask", "FastAPI",
    "Spring Boot", "Express.js", "Next.js", "HTML", "CSS", "Tailwind CSS",
    "Bootstrap", "Flutter", "React Native", "Android",
    # Data & ML / AI
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "SQLite",
    "Pandas", "NumPy", "Scikit-learn", "TensorFlow", "Keras", "PyTorch",
    "Spark", "Hadoop", "Airflow", "dbt", "Snowflake", "BigQuery",
    "Feature Engineering", "NLP", "Deep Learning", "Machine Learning",
    "Computer Vision", "OpenCV", "Transformers", "HuggingFace", "LangChain",
    "LlamaIndex", "Streamlit", "Matplotlib", "Seaborn", "Statistics",
    "A/B Testing", "Data Visualization", "ETL", "Data Pipelines",
    # Cloud & DevOps
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform",
    "CI/CD", "Jenkins", "GitHub Actions", "Linux", "Git", "GitHub", "Postman",
    "Firebase", "Supabase", "Vercel",
    # Data Viz & BI
    "Tableau", "Power BI", "Excel", "Jupyter",
    # Design
    "Figma", "Sketch", "Adobe XD", "Adobe Photoshop", "Adobe Illustrator",
    "InVision", "Wireframing", "Prototyping", "User Research",
    "Usability Testing", "Design Systems", "Typography", "Color Theory",
    "Responsive Design", "Design Thinking", "Brand Identity",
    # Marketing
    "SEO", "SEM", "Google Analytics", "Google Ads", "Facebook Ads",
    "Content Strategy", "Copywriting", "Social Media Marketing",
    "Email Marketing", "Marketing Automation", "HubSpot",
    # Sales & Business
    "Salesforce", "CRM", "Cold Calling", "Pipeline Management", "Negotiation",
    "Account Management", "B2B Sales", "B2C Sales", "Solution Selling",
    # General
    "REST APIs", "GraphQL", "Microservices", "Agile", "Scrum",
    "Project Management", "Problem Solving",
]

# Common job & internship titles for extraction
JOB_TITLES = [
    # Intern & Junior Roles
    "Machine Learning Intern", "Data Science Intern", "Software Engineering Intern",
    "Web Development Intern", "Frontend Intern", "Backend Intern", "AI Intern",
    "Research Intern", "Software Developer Intern", "Junior Software Engineer",
    "AI/ML Enthusiast", "Student Developer", "Associate Software Engineer",
    # Engineering
    "Software Engineer", "Senior Software Engineer", "Backend Developer",
    "Frontend Developer", "Full Stack Developer", "DevOps Engineer",
    "Site Reliability Engineer", "Software Architect", "Mobile Developer",
    "Android Developer", "Flutter Developer", "iOS Developer",
    "Cloud Engineer", "Platform Engineer",
    # Data & AI
    "Data Analyst", "Senior Data Analyst", "Business Intelligence Analyst",
    "Data Scientist", "Machine Learning Engineer", "Analytics Engineer",
    "Quantitative Analyst", "Research Analyst", "Data Engineer",
    "AI Engineer", "Deep Learning Engineer",
    # Marketing & Sales
    "Marketing Manager", "Digital Marketing Specialist", "Content Marketing Manager",
    "SEO Specialist", "Social Media Manager", "Growth Marketing Manager",
    "Sales Representative", "Account Executive", "Sales Manager",
    "Business Development Representative", "Regional Sales Manager",
    # Design
    "UI/UX Designer", "Senior Product Designer", "Visual Designer",
    "Graphic Designer", "Interaction Designer", "UX Researcher",
]

# Education keywords
EDUCATION_PATTERNS = [
    r"(?:B\.?Tech(?:nology)?|B\.?E\.?|Bachelor(?:'s)?(?:\s+of\s+Technology|\s+of\s+Engineering)?)\s*(?:\([A-Za-z\s]+\))?(?:\s+in\s+[\w\s\-]+)?",
    r"(?:B\.?S\.?|Bachelor(?:'s)?(?:\s+of\s+Science)?)\s+(?:in\s+)?[\w\s\-]+",
    r"(?:M\.?Tech(?:nology)?|M\.?E\.?|Master(?:'s)?(?:\s+of\s+Technology|\s+of\s+Engineering)?)",
    r"(?:M\.?S\.?|Master(?:'s)?(?:\s+of\s+Science)?)\s+(?:in\s+)?[\w\s\-]+",
    r"(?:B\.?C\.?A\.?|Bachelor\s+of\s+Computer\s+Applications)",
    r"(?:M\.?C\.?A\.?|Master\s+of\s+Computer\s+Applications)",
    r"(?:B\.?A\.?|Bachelor(?:'s)?(?:\s+of\s+Arts)?)\s+(?:in\s+)?[\w\s\-]+",
    r"(?:M\.?B\.?A\.?|Master(?:'s)?(?:\s+of\s+Business\s+Administration)?)",
    r"(?:Ph\.?D\.?|Doctor(?:ate)?)\s+(?:in\s+)?[\w\s\-]+",
]

# Experience years patterns
EXPERIENCE_PATTERNS = [
    r"(\d+)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?experience",
    r"(\d+)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:professional\s+)?experience",
    r"experience.*?(\d+)\+?\s*(?:years?|yrs?)",
    r"(\d+)\+?\s*(?:years?|yrs?)\s+in\s+",
]

# Technical terms and section headers to reject as candidate names
NAME_BLOCKLIST = {
    "machine", "learning", "deep", "artificial", "intelligence", "python", "java",
    "cloud", "streamlit", "linux", "scripting", "developed", "built", "managed",
    "curriculum", "vitae", "resume", "education", "experience", "projects", "skills",
    "summary", "objective", "certifications", "technologies", "profile", "contact",
    "flutter", "android", "react", "github", "linkedin", "email", "phone", "address",
    "software", "engineer", "developer", "student", "btech", "b.tech", "cse",
    "ahmedabad", "gujarat", "mumbai", "delhi", "india", "portfolio", "faculty",
    "engineering", "university", "institute", "college", "problem", "solving"
}


def clean_name_from_filename(filename: str) -> str:
    """Extract and format candidate name from standard resume filenames."""
    if not filename:
        return ""
    base = os.path.basename(filename)
    name_part, _ = os.path.splitext(base)

    # If there is a hyphen separator like "... - DHYEY CHAVADIYA", take the portion after the hyphen
    if " - " in name_part:
        name_part = name_part.split(" - ")[-1]

    # Strip institutional prefix like B.Tech(CSE)_202302626010003_ or roll numbers
    name_part = re.sub(r'^[A-Za-z0-9\.\(\)\-_]+_\d{5,}_?', '', name_part)
    name_part = re.sub(r'^[A-Za-z0-9\.\(\)\-_]+-\d{5,}_?', '', name_part)
    name_part = re.sub(r'^\d{5,}_?', '', name_part)

    # Strip trailing labels like _Resume, -Resume, _Updated, (1), etc.
    name_part = re.sub(r'[\-_\s]+(?:Resume|CV|Updated|Latest|Official|Final|PDF).*$', '', name_part, flags=re.IGNORECASE)
    name_part = re.sub(r'\(\d+\)$', '', name_part)

    # Clean leading/trailing punctuation and underscores
    name_part = name_part.replace("_", " ").strip("- _")

    # Handle camelCase like AmulyaAnamdasu -> Amulya Anamdasu
    if " " not in name_part and re.search(r'[a-z][A-Z]', name_part):
        name_part = re.sub(r'([a-z])([A-Z])', r'\1 \2', name_part)

    # Validate characters
    if re.match(r'^[A-Za-z\s\.\'-]{2,50}$', name_part):
        words = name_part.split()
        if 1 <= len(words) <= 5:
            # Reject if composed entirely of blocklisted words
            if not all(w.lower() in NAME_BLOCKLIST for w in words):
                return " ".join(w.capitalize() for w in words)
    return ""


class ResumeNERExtractor:
    """Extracts structured entities from resume text using spaCy + hybrid rules."""

    def __init__(self, model_name: str = "en_core_web_sm"):
        """Initialize the extractor with spaCy model and phrase matchers."""
        self.nlp = spacy.load(model_name)

        # Build skills phrase matcher
        self.skill_matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
        patterns = [self.nlp.make_doc(skill) for skill in SKILLS_LIST]
        self.skill_matcher.add("SKILLS", patterns)

        # Build job title phrase matcher
        self.title_matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
        title_patterns = [self.nlp.make_doc(title) for title in JOB_TITLES]
        self.title_matcher.add("TITLES", title_patterns)

    def extract_name(self, doc, raw_text: str = "", source_file: str = "") -> str:
        """
        Extract candidate name using a 3-tier hybrid strategy:
        1. Clean candidate name from source filename (highest accuracy for structured batches).
        2. Top-header text line inspection (first 10 lines, avoiding tech stop-words).
        3. Strict spaCy PERSON entity extraction from the header zone.
        """
        # Tier 1: Filename
        if source_file:
            from_file = clean_name_from_filename(source_file)
            if from_file:
                return from_file

        # Tier 2: Inspect first 10 lines of text
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
        for line in lines[:10]:
            # Clean symbols and bullets
            cleaned = re.sub(r'^[●•\-\*\d\.\s\|]+', '', line).strip()
            # Skip lines containing contact info or digits
            if "@" in cleaned or "http" in cleaned or re.search(r'\d', cleaned) or "|" in cleaned:
                continue
            words = cleaned.split()
            # Candidate names typically have 2-4 words and 3-40 characters
            if 2 <= len(words) <= 4 and 3 <= len(cleaned) <= 40:
                if re.match(r'^[A-Za-z\s\.\'-]+$', cleaned):
                    # Check that none of the words are in NAME_BLOCKLIST
                    if not any(w.lower() in NAME_BLOCKLIST for w in words):
                        return " ".join(w.capitalize() for w in words)

        # Tier 3: spaCy PERSON entities (only from the first 600 characters)
        header_text = raw_text[:600]
        header_doc = self.nlp(header_text)
        for ent in header_doc.ents:
            if ent.label_ == "PERSON":
                ent_clean = ent.text.strip()
                words = ent_clean.split()
                if 2 <= len(words) <= 4 and re.match(r'^[A-Za-z\s\.\'-]+$', ent_clean):
                    if not any(w.lower() in NAME_BLOCKLIST for w in words):
                        return " ".join(w.capitalize() for w in words)

        # Fallback
        if lines:
            first = lines[0]
            words = first.split()
            if 1 <= len(words) <= 3 and not any(w.lower() in NAME_BLOCKLIST for w in words):
                return " ".join(w.capitalize() for w in words)

        return "Candidate"

    def extract_skills(self, doc) -> list:
        """Extract skills using PhraseMatcher."""
        matches = self.skill_matcher(doc)
        skills = set()
        for match_id, start, end in matches:
            span = doc[start:end]
            skills.add(span.text.title() if len(span.text) > 3 else span.text.upper())
        return sorted(skills)

    def extract_education(self, text: str) -> str:
        """Extract education level using regex patterns."""
        for pattern in EDUCATION_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                edu = match.group(0).strip()
                edu = re.sub(r'\s+', ' ', edu).strip()
                if len(edu) > 80:
                    edu = edu[:80]
                return edu
        return "B.Tech Computer Science (or equivalent)"

    def extract_experience_years(self, text: str) -> float:
        """Extract years of experience from text."""
        for pattern in EXPERIENCE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    yrs = float(match.group(1))
                    if 0.0 <= yrs <= 25.0:
                        return yrs
                except (ValueError, IndexError):
                    continue

        # Inspect ONLY the work experience or internship section (exclude education dates)
        exp_match = re.search(
            r'(?:work\s+experience|professional\s+experience|employment\s+history|internships?)\s*[:\n](.*?)(?:education|academic|projects|skills|certifications|awards|\Z)',
            text,
            re.IGNORECASE | re.DOTALL
        )
        if exp_match:
            exp_section = exp_match.group(1)
            # Check for months format e.g. "6 months" or "3 mos"
            months_found = [int(m) for m in re.findall(r'(\d+)\s*(?:months?|mos?)\b', exp_section, re.IGNORECASE)]
            if months_found:
                return round(sum(months_found) / 12.0, 1)

            # Year ranges like 2023 - 2024 or 2024 - Present
            year_ranges = re.findall(r'((?:19|20)\d{2})\s*(?:-|–|to)\s*((?:19|20)\d{2}|present)', exp_section, re.IGNORECASE)
            total_yrs = 0.0
            for start_str, end_str in year_ranges:
                s_yr = int(start_str)
                e_yr = 2026 if "present" in end_str.lower() else int(end_str)
                if 0 <= (e_yr - s_yr) <= 10:
                    total_yrs += (e_yr - s_yr)
            if total_yrs > 0:
                return min(total_yrs, 10.0)

        return 0.0

    def extract_most_recent_title(self, doc, raw_text: str = "") -> str:
        """Extract most recent job or internship title, or default to candidate's discipline."""
        matches = self.title_matcher(doc)
        if matches:
            _, start, end = matches[0]
            return doc[start:end].text.title()

        # Check for student / aspirant cues in text
        lower = raw_text[:2000].lower()
        if "b.tech" in lower or "computer science" in lower or "student" in lower:
            return "Computer Science Student / Aspiring Engineer"
        elif "data" in lower or "analytics" in lower:
            return "Aspiring Data Analyst"

        return "Junior Developer"

    def extract(self, raw_text: str, source_file: str = "") -> dict:
        """
        Extract all structured information from raw resume text.

        Returns:
            {
                "name": str,
                "skills": [str, ...],
                "education": str,
                "experience_years": float,
                "most_recent_title": str
            }
        """
        doc = self.nlp(raw_text[:100000])

        return {
            "name": self.extract_name(doc, raw_text=raw_text, source_file=source_file),
            "skills": self.extract_skills(doc),
            "education": self.extract_education(raw_text),
            "experience_years": self.extract_experience_years(raw_text),
            "most_recent_title": self.extract_most_recent_title(doc, raw_text=raw_text),
        }


# Module-level singleton
_extractor = None


def get_extractor() -> ResumeNERExtractor:
    """Get or create the module-level extractor singleton."""
    global _extractor
    if _extractor is None:
        _extractor = ResumeNERExtractor()
    return _extractor


def extract_from_text(raw_text: str, source_file: str = "") -> dict:
    """Convenience function to extract entities from raw text."""
    return get_extractor().extract(raw_text, source_file=source_file)


if __name__ == "__main__":
    sample = """
    John Smith
    john.smith@email.com | (555) 123-4567 | San Francisco, CA

    Senior Software Engineer with 8+ years of experience in software engineering.
    Proficient in Python, Django, PostgreSQL, and Docker.

    WORK EXPERIENCE
    Senior Software Engineer — Acme Corp (Jan 2020 – Present)
    • Developed REST APIs using Django and PostgreSQL
    • Managed CI/CD pipelines with Jenkins and Docker
    """
    result = extract_from_text(sample, source_file="John_Smith_Resume.pdf")
    print("Test extraction:")
    for k, v in result.items():
        print(f"  {k}: {v}")
