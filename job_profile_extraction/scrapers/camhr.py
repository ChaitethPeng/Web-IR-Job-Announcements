import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import re
import time

import requests

from job_profile_extraction.models import RawJobAd

API_BASE = "https://api.camhr.com/v1.0.0"
SITE_BASE = "https://www.camhr.com/a/job"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AcademicJobResearchBot/1.0; +contact: student-project)",
    "Accept": "application/json",
}

# CamHR's listing endpoint accepts up to size=100 per page, so a full sweep of
# ~1500 jobs only needs ~16 requests.
LISTING_PAGE_SIZE = 100


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def get_json(url, delay=0.3):
    time.sleep(delay)
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()


def get_category_directory():
    """CATEGORY lookup table from CamHR's own constants endpoint - the job
    category taxonomy used by every job's categoryId field."""
    data = get_json(f"{API_BASE}/application/constants", delay=0)
    categories = []
    for entry in data.get("CATEGORY", {}).values():
        categories.append({
            "category_id": entry.get("value"),
            "category": entry.get("label"),
        })
    categories.sort(key=lambda c: c["category_id"])
    return categories


def get_job_ids(max_listing_pages=None):
    """Page through the listing API and return every job id (and its
    lightweight summary fields). max_listing_pages limits how many size=100
    pages to fetch (falsy/None = all)."""
    ids = []
    page = 1

    while True:
        data = get_json(f"{API_BASE}/jobs/simple/page-query?page={page}&size={LISTING_PAGE_SIZE}")
        payload = data.get("data", {})
        result = payload.get("result", [])

        ids.extend(item["id"] for item in result)

        total_pages = payload.get("totalPage", page)
        if max_listing_pages and page >= max_listing_pages:
            break
        if page >= total_pages or not result:
            break
        page += 1

    return ids


def label(field):
    if isinstance(field, dict):
        return clean_text(field.get("label", ""))
    return ""


def scrape_detail(job_id):
    data = get_json(f"{API_BASE}/jobs/{job_id}")
    job = data.get("data")
    if not job:
        return None

    employer = job.get("employer") or {}

    description = clean_text(job.get("description", ""))
    requirement = clean_text(job.get("requirement", ""))
    full_description = description
    if requirement:
        full_description = f"{description}\n\nRequirement:\n{requirement}" if description else requirement

    languages_required = []
    for lang in job.get("jobLangs") or []:
        lang_label = label(lang.get("languageId"))
        level_label = label(lang.get("languageLevelId"))
        if lang_label:
            languages_required.append(f"{lang_label} - {level_label}" if level_label else lang_label)

    qualifications_required = []
    qualification_label = label(job.get("qualificationId"))
    if qualification_label:
        qualifications_required.append(qualification_label)
    others_qualification = clean_text(job.get("othersQualification") or "")
    if others_qualification:
        qualifications_required.append(others_qualification)

    work_history = []
    workyears = job.get("workyears")
    if workyears:
        work_history.append(f"{workyears} year(s) experience")

    expdate = job.get("expdate") or ""
    deadline = expdate[:10] if expdate else ""

    location = clean_text(job.get("address", "")) or label(employer.get("locationId"))

    return RawJobAd(
        source="camhr",
        title=clean_text(job.get("title", "")),
        company=clean_text(employer.get("company", "")),
        location=location,
        salary=label(job.get("salaryId")),
        deadline=deadline,
        url=f"{SITE_BASE}/{job_id}",
        description=full_description,
        career_categories=[label(job.get("categoryId"))] if label(job.get("categoryId")) else [],
        industry=label(employer.get("industrialId")),
        schedule=label(job.get("termId")),
        languages_required=languages_required,
        qualifications_required=qualifications_required,
        work_history=work_history,
    )


def scrape(pages=1):
    """pages limits how many size=100 listing pages to sweep (falsy/0/None =
    every job on the site, ~1500 jobs / ~16 listing pages)."""
    job_ids = get_job_ids(max_listing_pages=pages)
    print(f"CamHR: {len(job_ids)} job ids collected")

    jobs = []
    for job_id in job_ids:
        try:
            job = scrape_detail(job_id)
            if job:
                jobs.append(job)
        except Exception as e:
            print("  skip job:", job_id, e)

    return jobs


if __name__ == "__main__":
    jobs = scrape(pages=1)
    print("\nTotal jobs:", len(jobs))
