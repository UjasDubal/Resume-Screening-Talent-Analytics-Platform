"""
Synthetic Job Description Generator
=====================================
Generates 18 synthetic job descriptions across 5 job families:
  - Software Engineering (4 JDs)
  - Data Analysis (4 JDs)
  - Marketing (4 JDs)
  - Sales (3 JDs)
  - Design (3 JDs)

Output: data/synthetic_jobs.json
"""

import os
import json
import random
from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)


JOB_TEMPLATES = {
    "Software Engineering": [
        {
            "title": "Senior Backend Engineer",
            "department": "Engineering",
            "required_skills": ["Python", "Django", "PostgreSQL", "Docker", "REST APIs", "Git", "AWS"],
            "required_experience": 5,
            "description_template": (
                "We are looking for a Senior Backend Engineer to design and build scalable "
                "backend systems. You will work closely with product and frontend teams to "
                "deliver reliable APIs and data pipelines. Experience with cloud-native "
                "architectures and containerization is essential."
            ),
        },
        {
            "title": "Full Stack Developer",
            "department": "Engineering",
            "required_skills": ["JavaScript", "React", "Node.js", "TypeScript", "PostgreSQL", "Git", "Docker"],
            "required_experience": 3,
            "description_template": (
                "Join our product team as a Full Stack Developer. You will build and "
                "maintain user-facing features end-to-end, from database to UI. We value "
                "clean code, automated testing, and collaborative development."
            ),
        },
        {
            "title": "DevOps Engineer",
            "department": "Infrastructure",
            "required_skills": ["Docker", "Kubernetes", "Terraform", "CI/CD", "AWS", "Linux", "Python"],
            "required_experience": 4,
            "description_template": (
                "We need a DevOps Engineer to build and maintain our CI/CD pipelines, "
                "manage cloud infrastructure, and improve deployment reliability. You will "
                "work with engineering teams to automate everything from testing to production."
            ),
        },
        {
            "title": "Junior Software Engineer",
            "department": "Engineering",
            "required_skills": ["Python", "Git", "SQL", "REST APIs", "Linux"],
            "required_experience": 1,
            "description_template": (
                "We're hiring a Junior Software Engineer to join our growing team. "
                "You'll contribute to backend services, write tests, and learn from "
                "senior engineers. A passion for clean code and continuous learning is key."
            ),
        },
    ],
    "Data Analysis": [
        {
            "title": "Senior Data Analyst",
            "department": "Analytics",
            "required_skills": ["SQL", "Python", "Tableau", "Statistics", "Excel", "A/B Testing"],
            "required_experience": 4,
            "description_template": (
                "We are looking for a Senior Data Analyst to drive data-informed decisions "
                "across the organization. You will design dashboards, run A/B tests, and "
                "present actionable insights to leadership."
            ),
        },
        {
            "title": "Machine Learning Engineer",
            "department": "Data Science",
            "required_skills": ["Python", "Scikit-learn", "TensorFlow", "SQL", "Docker", "Feature Engineering", "Git"],
            "required_experience": 0,
            "description_template": (
                "Join us as a Machine Learning Engineer to build and deploy ML models "
                "that power our core product features. You will design feature pipelines, "
                "train models, and monitor production performance."
            ),
        },
        {
            "title": "Data Engineer",
            "department": "Engineering",
            "required_skills": ["Python", "SQL", "Spark", "Airflow", "AWS", "ETL", "Docker"],
            "required_experience": 3,
            "description_template": (
                "We need a Data Engineer to build and maintain our data infrastructure. "
                "You will design ETL pipelines, optimize data warehouses, and ensure data "
                "quality and availability for analytics and ML teams."
            ),
        },
        {
            "title": "Business Intelligence Analyst",
            "department": "Business Operations",
            "required_skills": ["SQL", "Power BI", "Excel", "Data Visualization", "Statistics"],
            "required_experience": 2,
            "description_template": (
                "We're looking for a BI Analyst to transform raw data into actionable "
                "business insights. You will build reports, create dashboards, and support "
                "cross-functional teams with data-driven recommendations."
            ),
        },
    ],
    "Marketing": [
        {
            "title": "Digital Marketing Manager",
            "department": "Marketing",
            "required_skills": ["Google Analytics", "SEO", "Google Ads", "Content Strategy", "Email Marketing", "A/B Testing"],
            "required_experience": 5,
            "description_template": (
                "Lead our digital marketing efforts across all channels. You will manage "
                "campaigns, optimize conversion funnels, and drive measurable growth through "
                "data-driven marketing strategies."
            ),
        },
        {
            "title": "Content Marketing Specialist",
            "department": "Marketing",
            "required_skills": ["Copywriting", "SEO", "WordPress", "Social Media Marketing", "Content Strategy"],
            "required_experience": 2,
            "description_template": (
                "Join our content team to create compelling blog posts, whitepapers, and "
                "social media content. You will develop and execute a content calendar that "
                "drives organic traffic and brand awareness."
            ),
        },
        {
            "title": "Growth Marketing Manager",
            "department": "Growth",
            "required_skills": ["Google Ads", "Facebook Ads", "A/B Testing", "Marketing Automation", "HubSpot", "Lead Generation"],
            "required_experience": 4,
            "description_template": (
                "We need a Growth Marketing Manager to scale our acquisition channels. "
                "You will run paid campaigns, optimize CAC, and build automated nurture "
                "sequences that convert leads into customers."
            ),
        },
        {
            "title": "SEO Specialist",
            "department": "Marketing",
            "required_skills": ["SEO", "Google Analytics", "Content Strategy", "Market Research", "WordPress"],
            "required_experience": 2,
            "description_template": (
                "Optimize our web presence for search engines. You will conduct keyword "
                "research, implement on-page and technical SEO improvements, and track "
                "rankings across priority terms."
            ),
        },
    ],
    "Sales": [
        {
            "title": "Enterprise Account Executive",
            "department": "Sales",
            "required_skills": ["Salesforce", "Solution Selling", "Negotiation", "Pipeline Management", "B2B Sales", "Presentation Skills"],
            "required_experience": 6,
            "description_template": (
                "Close six- and seven-figure enterprise deals. You will manage complex "
                "sales cycles, build relationships with C-level executives, and consistently "
                "exceed quarterly quotas."
            ),
        },
        {
            "title": "Sales Development Representative",
            "department": "Sales",
            "required_skills": ["Cold Calling", "Lead Generation", "CRM Management", "Prospecting", "HubSpot"],
            "required_experience": 1,
            "description_template": (
                "Generate qualified pipeline for our sales team. You will prospect via "
                "phone, email, and social channels, qualify inbound leads, and book "
                "discovery meetings with decision-makers."
            ),
        },
        {
            "title": "Regional Sales Manager",
            "department": "Sales",
            "required_skills": ["Account Management", "Territory Management", "Revenue Forecasting", "Salesforce", "Strategic Planning", "Negotiation"],
            "required_experience": 7,
            "description_template": (
                "Lead a team of account executives across the region. You will set sales "
                "strategy, coach reps, manage forecasting, and be accountable for regional "
                "revenue targets."
            ),
        },
    ],
    "Design": [
        {
            "title": "Senior Product Designer",
            "department": "Design",
            "required_skills": ["Figma", "User Research", "Prototyping", "Design Systems", "Usability Testing", "Wireframing"],
            "required_experience": 5,
            "description_template": (
                "Shape the user experience of our flagship product. You will conduct user "
                "research, create wireframes and high-fidelity prototypes, and collaborate "
                "closely with engineering to ship polished features."
            ),
        },
        {
            "title": "UI/UX Designer",
            "department": "Design",
            "required_skills": ["Figma", "Adobe XD", "Wireframing", "Prototyping", "HTML", "CSS", "Responsive Design"],
            "required_experience": 3,
            "description_template": (
                "Design intuitive, beautiful interfaces for our web and mobile products. "
                "You will translate user needs into pixel-perfect designs and work with "
                "developers to ensure faithful implementation."
            ),
        },
        {
            "title": "Visual Designer",
            "department": "Creative",
            "required_skills": ["Adobe Photoshop", "Adobe Illustrator", "Typography", "Color Theory", "Brand Identity", "Figma"],
            "required_experience": 2,
            "description_template": (
                "Create stunning visual assets across our brand touchpoints. From marketing "
                "materials to product illustrations, you will ensure a consistent and "
                "elevated brand presence."
            ),
        },
    ],
}


def generate_jobs(output_path: str):
    """Generate synthetic job descriptions and save to JSON."""
    jobs = []
    job_id = 1

    for family_name, templates in JOB_TEMPLATES.items():
        for template in templates:
            company = fake.company()
            location = f"{fake.city()}, {fake.state_abbr()}"

            job = {
                "job_id": job_id,
                "title": template["title"],
                "department": template["department"],
                "job_family": family_name,
                "company": company,
                "location": location,
                "required_skills": template["required_skills"],
                "required_experience": template["required_experience"],
                "description": template["description_template"],
                "responsibilities": [
                    f"Collaborate with cross-functional teams to deliver high-impact projects",
                    f"Contribute to best practices and team knowledge sharing",
                    f"Participate in code reviews and design discussions" if "Engineer" in template["title"] or "Developer" in template["title"]
                    else f"Report on key metrics and drive continuous improvement",
                ],
                "benefits": [
                    "Competitive salary and equity",
                    "Health, dental, and vision insurance",
                    "Flexible remote work policy",
                    "Professional development budget",
                ],
                "posted_date": str(fake.date_between(start_date="-90d", end_date="today")),
            }
            jobs.append(job)
            job_id += 1

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(jobs, f, indent=2)

    print(f"[OK] Generated {len(jobs)} job descriptions in {output_path}")
    return jobs


if __name__ == "__main__":
    output_path = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_jobs.json")
    generate_jobs(output_path)
