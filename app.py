import json
from pathlib import Path

from flask import Flask, jsonify, render_template, request

PROJECT_ROOT = Path(__file__).resolve().parent
RAW_JOBS_PATH = PROJECT_ROOT / "data" / "raw" / "jobs_raw.json"
PROFILES_PATH = PROJECT_ROOT / "data" / "output" / "job_profiles.json"

app = Flask(__name__)

# Category labels vary per source site (BongThom, CamHR and Khmer24 each run
# their own taxonomy), so job postings get bucketed into this fixed set for
# the sidebar filter instead of showing ~150 raw source category names.
CATEGORY_BUCKETS = ["Accounting", "IT", "Engineering", "Sales", "Finance", "HR", "Admin", "Others"]

BUCKET_RULES = [
    ("Accounting", ("account", "audit", "tax")),
    ("IT", ("computer", "information technology", "programming", "software",
            "website", "network", "telecommunication", " it ")),
    ("Engineering", ("engineer", "architecture", "construction", "manufactur",
                      "quality control", "mechanic", "technician", "maintenance")),
    ("Sales", ("sales", "marketing", "merchandis")),
    ("Finance", ("finance", "banking", "insurance", "economic")),
    ("HR", ("human resource", "hr")),
    ("Admin", ("admin", "assistant", "secretary", "business administration",
               "management", "executive", "exec.", "operations")),
]


def bucket_category(career_categories, title):
    haystack = f" {' '.join(career_categories)} {title or ''} ".lower()
    for bucket, keywords in BUCKET_RULES:
        if any(keyword in haystack for keyword in keywords):
            return bucket
    return "Others"


# Raw "location" values range from a clean "District, Phnom Penh" (Khmer24)
# to a full street address (CamHR/BongThom), which makes a location filter
# built straight from the raw text unusable (dozens of near-unique full
# addresses). Match against Cambodia's provinces instead so the dropdown
# stays to ~25 meaningful options; the untouched raw address still shows in
# the job detail panel.
PROVINCES = [
    ("Phnom Penh", ["Phnom Penh"]),
    ("Banteay Meanchey", ["Banteay Meanchey"]),
    ("Battambang", ["Battambang"]),
    ("Kampong Cham", ["Kampong Cham"]),
    ("Kampong Chhnang", ["Kampong Chhnang"]),
    ("Kampong Speu", ["Kampong Speu"]),
    ("Kampong Thom", ["Kampong Thom"]),
    ("Kampot", ["Kampot"]),
    ("Kandal", ["Kandal"]),
    ("Kep", ["Kep"]),
    ("Koh Kong", ["Koh Kong"]),
    ("Kratie", ["Kratie"]),
    ("Mondulkiri", ["Mondulkiri", "Mondul Kiri"]),
    ("Oddar Meanchey", ["Oddar Meanchey"]),
    ("Pailin", ["Pailin"]),
    ("Sihanoukville", ["Preah Sihanouk", "Sihanoukville"]),
    ("Preah Vihear", ["Preah Vihear"]),
    ("Prey Veng", ["Prey Veng"]),
    ("Pursat", ["Pursat"]),
    ("Ratanakiri", ["Ratanakiri", "Ratanak Kiri"]),
    ("Siem Reap", ["Siemreap", "Siem Reap"]),
    ("Stung Treng", ["Stung Treng"]),
    ("Svay Rieng", ["Svay Rieng"]),
    ("Takeo", ["Takeo"]),
    ("Tboung Khmum", ["Tboung Khmum"]),
]


def normalize_location(location):
    if not location:
        return ""
    lowered = location.lower()
    for canonical, aliases in PROVINCES:
        if any(alias.lower() in lowered for alias in aliases):
            return canonical
    return "Other"


def load_json(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def merge_key(row):
    return (row.get("url") or "", row.get("title") or "")


def load_jobs():
    """Combine the structured scraper output (career_categories, benefits,
    qualifications_required, ...) with the keyword-extracted profile output
    (skills, technologies, ...) into the single shape the UI expects,
    preferring the more precise structured fields where both exist."""
    raw_rows = load_json(RAW_JOBS_PATH)
    profile_rows = load_json(PROFILES_PATH)
    profiles_by_key = {merge_key(p): p for p in profile_rows}

    jobs = []
    for i, raw in enumerate(raw_rows):
        profile = profiles_by_key.get(merge_key(raw), {})
        career_categories = raw.get("career_categories") or []

        jobs.append({
            "id": i,
            "source": raw.get("source", ""),
            "title": raw.get("title", ""),
            "company": raw.get("company", ""),
            "location": raw.get("location", ""),
            "location_area": normalize_location(raw.get("location", "")),
            "salary_information": raw.get("salary", "") or profile.get("salary_information", ""),
            "deadline": raw.get("deadline", ""),
            "url": raw.get("url", ""),
            "skills": profile.get("skills") or raw.get("soft_skills") or [],
            "technologies": profile.get("technologies") or [],
            "qualifications": raw.get("qualifications_required") or profile.get("qualifications") or [],
            "responsibilities": raw.get("responsibilities") or profile.get("responsibilities") or [],
            "benefits": raw.get("benefits") or [],
            "raw_text": raw.get("description") or profile.get("raw_text") or "",
            "career_categories": career_categories,
            "category": bucket_category(career_categories, raw.get("title", "")),
        })

    return jobs


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/jobs")
def api_jobs():
    jobs = load_jobs()

    q = request.args.get("q", "").strip().lower()
    source = request.args.get("source", "all")
    location = request.args.get("location", "all")
    category = request.args.get("category", "All")

    def matches(job):
        if category != "All" and job["category"] != category:
            return False
        if source != "all" and job["source"] != source:
            return False
        if location != "all" and job["location_area"] != location:
            return False
        if q:
            haystack = " ".join([
                job["title"], job["company"], job["location"],
                " ".join(job["skills"]), " ".join(job["technologies"]),
            ]).lower()
            if q not in haystack:
                return False
        return True

    filtered = [job for job in jobs if matches(job)]
    return jsonify(filtered)


@app.route("/api/meta")
def api_meta():
    """Facet values (sources, locations, category counts, totals) for
    populating the filter dropdowns and header stats without re-deriving
    them client-side from the full job list."""
    jobs = load_jobs()

    sources = sorted({job["source"] for job in jobs if job["source"]})
    locations = sorted(
        {job["location_area"] for job in jobs if job["location_area"]},
        key=lambda loc: (loc == "Other", loc),
    )
    skills = sorted({s for job in jobs for s in job["skills"]})

    category_counts = {c: 0 for c in CATEGORY_BUCKETS}
    for job in jobs:
        category_counts[job["category"]] = category_counts.get(job["category"], 0) + 1

    return jsonify({
        "total_jobs": len(jobs),
        "sources": sources,
        "locations": locations,
        "total_skills": len(skills),
        "categories": CATEGORY_BUCKETS,
        "category_counts": category_counts,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
