import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from job_profile_extraction.models import RawJobAd

BASE = "https://www.cambojob.com/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def get_session():
    """CamboJob serves a click-CAPTCHA page instead of real content to
    cookie-less/refererless requests (looks bot-like to their anti-bot
    heuristics). A normal browsing session - cookies from an earlier page,
    Referer set to that page - reliably avoids it; a bare one-off GET does
    not."""
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def get_with_retry(session, url, headers=None, attempts=3, backoff=4):
    """CamboJob's anti-bot heuristic occasionally 403s a perfectly normal
    request and then serves the same URL fine seconds later - transient, not
    a hard block. Retry with backoff instead of giving up immediately."""
    last_error = None
    for attempt in range(attempts):
        resp = session.get(url, headers=headers, timeout=20)
        if resp.status_code == 403:
            last_error = requests.HTTPError(f"403 Forbidden: {url}")
            time.sleep(backoff * (attempt + 1))
            continue
        resp.raise_for_status()
        return resp
    raise last_error


def get_city_listing_urls(session):
    """Homepage is a city x category filter matrix with no jobs of its own.
    Each bare "citycategory/<id>.htm" link (no /jobcategory/ suffix) is that
    city's "No Limit" (all categories) listing, which does show real jobs."""
    resp = get_with_retry(session, urljoin(BASE, "Jobs/jobs_list.htm"))
    time.sleep(1.5)

    soup = BeautifulSoup(resp.text, "html.parser")
    urls = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        match = re.fullmatch(r"/Jobs/jobs_list/citycategory/(\d+)\.htm", href)
        if not match:
            continue
        if match.group(1) in seen:
            continue
        seen.add(match.group(1))
        urls.append(urljoin(BASE, href))

    return urls


def get_detail_urls_for_city(session, city_url):
    resp = get_with_retry(session, city_url)
    time.sleep(1.5)

    soup = BeautifulSoup(resp.text, "html.parser")
    urls = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "jobs-show-" not in href:
            continue
        full_url = urljoin(BASE, href)
        if full_url in seen:
            continue
        seen.add(full_url)
        urls.append(full_url)

    return urls, resp.url


def extract_pairs(container):
    """Both the job's "Basic information" box and the employer's info box
    render as a flat list of <a>Label: Value</a> icon-links."""
    pairs = {}
    if not container:
        return pairs
    for a in container.find_all("a"):
        text = clean_text(a.get_text(" "))
        if ":" not in text:
            continue
        label, value = text.split(":", 1)
        pairs[label.strip().lower()] = value.strip()
    return pairs


def scrape_detail(session, url, referer):
    resp = get_with_retry(session, url, headers={"Referer": referer})
    time.sleep(1.5)

    soup = BeautifulSoup(resp.text, "html.parser")

    title_el = soup.select_one(".jobs_name")
    if not title_el:
        return None

    title = clean_text(title_el.get_text())

    salary_el = title_el.find_next_sibling("h4")
    salary = clean_text(salary_el.get_text()) if salary_el else ""

    basic_info = extract_pairs(soup.select_one(".job-news-body"))

    company = ""
    company_el = soup.select_one(".company-logo")
    if company_el:
        name_el = company_el.parent.select_one("h3 a")
        if name_el:
            company = clean_text(name_el.get_text())

    desc_el = soup.select_one(".job-desc .job-news-body")
    description = ""
    if desc_el:
        for br in desc_el.find_all("br"):
            br.replace_with("\n")
        description = clean_text(desc_el.get_text(" "))

    qualifications_required = []
    education = basic_info.get("education requirements", "")
    if education:
        qualifications_required.append(education)

    work_history = []
    experience = basic_info.get("work experience", "")
    if experience:
        work_history.append(experience)

    return RawJobAd(
        source="cambojob",
        title=title,
        company=company,
        location=basic_info.get("work location", ""),
        salary=salary,
        deadline="",
        url=url,
        description=description,
        schedule=basic_info.get("job type", ""),
        qualifications_required=qualifications_required,
        work_history=work_history,
    )


def scrape(pages=None):
    """pages limits how many city listings to process (falsy/0/None = all
    cities found on the homepage filter matrix, ~25)."""
    jobs = []
    seen_details = set()

    session = get_session()

    city_urls = get_city_listing_urls(session)
    print(f"CamboJob: {len(city_urls)} city listings found")

    if pages:
        city_urls = city_urls[:pages]

    for city_url in city_urls:
        print(f"City listing: {city_url}")

        try:
            detail_urls, referer = get_detail_urls_for_city(session, city_url)
        except Exception as e:
            print("  skip city:", city_url, e)
            continue

        print(f"  ads found: {len(detail_urls)}")

        for detail_url in detail_urls:
            if detail_url in seen_details:
                continue
            seen_details.add(detail_url)

            try:
                job = scrape_detail(session, detail_url, referer)
                if job:
                    jobs.append(job)
                    print(f"  scraped: {detail_url}")
            except Exception as e:
                print("  skip detail:", detail_url, e)

    return jobs


if __name__ == "__main__":
    jobs = scrape(pages=2)
    print("\nTotal jobs:", len(jobs))
