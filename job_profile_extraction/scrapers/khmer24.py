import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import re
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from job_profile_extraction.models import RawJobAd

BASE = "https://www.khmer24.com/"
JOBS_INDEX_URL = urljoin(BASE, "en/c-jobs")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Every khmer24 page sits behind a Cloudflare JS challenge. A fresh browser
# session passes it once, but a second driver.get() in that SAME session gets
# stuck on the challenge indefinitely - so each detail page needs its own
# fresh browser (~10-15s each). Listing pages don't have this problem because
# loading more results happens via in-page scrolling, not a new navigation.
# These caps keep a default run to a "sample" scale rather than many hours.
MAX_ADS_PER_CATEGORY = 15
MAX_SCROLLS = 8
STAGNANT_SCROLL_LIMIT = 3
DETAIL_LOAD_ATTEMPTS = 3
LISTING_LOAD_ATTEMPTS = 3


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument(f"--user-agent={USER_AGENT}")
    options.add_argument("--disable-blink-features=AutomationControlled")

    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )


def get_categories(driver=None):
    """Job category slugs from the /en/c-jobs sidebar. Khmer24 doesn't show
    per-category counts anywhere in the UI (unlike BongThom), so - unlike
    bongthom.get_category_directory() - there's no site-wide count to report
    here; demand ranking has to be computed from what we actually scrape."""
    owns_driver = driver is None
    if owns_driver:
        driver = get_driver()

    try:
        driver.get(JOBS_INDEX_URL)
        time.sleep(6)
        soup = BeautifulSoup(driver.page_source, "html.parser")

        categories = []
        seen_slugs = set()

        for a in soup.find_all("a", href=True):
            match = re.search(r"/en/c-jobs-([a-z0-9-]+)", a["href"])
            if not match:
                continue
            slug = match.group(1)
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)

            name = clean_text(a.get_text())
            if not name:
                continue

            categories.append({
                "category": name,
                "slug": slug,
                "url": urljoin(BASE, f"en/c-jobs-{slug}"),
            })

        return categories

    finally:
        if owns_driver:
            driver.quit()


def wait_for_ad_links(driver, timeout=20, interval=1):
    """The ad grid hydrates client-side after the initial page load, and how
    long that takes is inconsistent (headless Chrome + Cloudflare's own JS
    delay) - a fixed sleep sometimes reads the DOM before any ads have
    rendered. Poll instead of guessing a fixed wait."""
    waited = 0
    while waited < timeout:
        if "adid-" in driver.page_source:
            return True
        time.sleep(interval)
        waited += interval
    return False


def get_detail_urls_for_category(driver, category_url, max_ads=MAX_ADS_PER_CATEGORY):
    """Load a category listing once, then scroll in-place to trigger its
    infinite-scroll loading until no new ads appear for a few rounds in a
    row, or max_ads is reached."""
    driver.get(f"{category_url}?page=1")
    wait_for_ad_links(driver)

    seen = {}
    stagnant_rounds = 0

    for _ in range(MAX_SCROLLS):
        soup = BeautifulSoup(driver.page_source, "html.parser")
        new_found = False

        for a in soup.find_all("a", href=True):
            match = re.search(r"/en/([a-z0-9-]+-adid-(\d+))", a["href"])
            if not match:
                continue
            ad_id = match.group(2)
            if ad_id not in seen:
                seen[ad_id] = urljoin(BASE, "en/" + match.group(1))
                new_found = True

        if len(seen) >= max_ads:
            break

        if new_found:
            stagnant_rounds = 0
        else:
            stagnant_rounds += 1
            if stagnant_rounds >= STAGNANT_SCROLL_LIMIT:
                break

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

    return list(seen.values())[:max_ads]


def extract_dl_pairs(section):
    pairs = {}
    for dl in section.find_all("dl"):
        dt = dl.find("dt")
        dd = dl.find("dd")
        if dt and dd:
            pairs[clean_text(dt.get_text())] = clean_text(dd.get_text())
    return pairs


def parse_detail(html, url):
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.find("h1")
    title = clean_text(title_el.get_text()) if title_el else ""
    if not title:
        return None

    time_el = soup.find("time")
    meta_row = time_el.parent if time_el else None

    location = ""
    if meta_row:
        for p in meta_row.find_all("p"):
            if p.find("span", class_=lambda c: c and "location" in c):
                location = clean_text(p.get_text())
                break

    salary_el = soup.select_one("p.font-semibold.text-error-500")
    salary = clean_text(salary_el.get_text()) if salary_el else ""

    description_heading = None
    for h2 in soup.find_all("h2"):
        if clean_text(h2.get_text()) == "Description":
            description_heading = h2
            break

    career_categories = []
    schedule = ""
    work_history = []
    description = ""

    if description_heading:
        section = description_heading.parent
        pairs = extract_dl_pairs(section)

        category = pairs.get("Category", "")
        if category:
            career_categories.append(category)

        schedule = pairs.get("Job Type", "")

        experience = pairs.get("Experience", "")
        if experience:
            work_history.append(experience)

        desc_paragraphs = section.find_all("p", recursive=False)
        if desc_paragraphs:
            description = clean_text(desc_paragraphs[0].get_text())

    company = ""
    profile_link = soup.select_one('a[title="View Profile"]')
    if profile_link:
        name_el = profile_link.select_one("p.font-bold")
        if name_el:
            company = clean_text(name_el.get_text())

    return RawJobAd(
        source="khmer24",
        title=title,
        company=company,
        location=location,
        salary=salary,
        deadline="",
        url=url,
        description=description,
        career_categories=career_categories,
        schedule=schedule,
        work_history=work_history,
    )


def _load_detail_html(url):
    driver = get_driver()
    try:
        driver.get(url)
        html = ""
        for _ in range(DETAIL_LOAD_ATTEMPTS):
            time.sleep(4)
            if driver.title != "Just a moment...":
                html = driver.page_source
                break
        else:
            return ""

        # Title resolving doesn't guarantee the content below it has
        # hydrated yet - poll for the "Description" section too.
        waited = 0
        while "Description" not in html and waited < 12:
            time.sleep(2)
            waited += 2
            html = driver.page_source

        return html
    finally:
        driver.quit()


def scrape_detail(url):
    """Every khmer24 page needs a fresh browser to clear Cloudflare's
    challenge - see the module docstring-ish comment above MAX_ADS_PER_CATEGORY.
    Cloudflare's challenge is flaky against headless Chrome, so retry with a
    brand new browser a couple times before giving up on this ad."""
    for _ in range(LISTING_LOAD_ATTEMPTS):
        html = _load_detail_html(url)
        if "Description" in html:
            return parse_detail(html, url)
    return None


def scrape(pages=None, max_ads_per_category=MAX_ADS_PER_CATEGORY):
    """pages limits how many job categories to process (falsy/0/None = all
    ~35). max_ads_per_category caps ads per category to keep runs sample-sized
    given the ~10-15s cost of every detail page (see module notes).

    Every driver.get() to a fresh top-level URL needs its own brand-new
    browser - reusing one Selenium session across categories (or across
    category -> detail) reliably gets stuck on Cloudflare's challenge past
    the first navigation. Only in-page scrolling within an already-loaded
    page is safe to reuse, which is what get_detail_urls_for_category does
    internally."""
    jobs = []
    seen_urls = set()

    categories = get_categories()
    print(f"Khmer24: {len(categories)} job categories found")

    if pages:
        categories = categories[:pages]

    for cat in categories:
        print(f"Category: {cat['category']}")

        # Cloudflare's challenge is flaky against headless Chrome - it
        # doesn't always clear within the wait even when the exact same
        # request would succeed on a retry, so give each category a few
        # fresh-browser attempts before giving up on it.
        detail_urls = []
        for attempt in range(LISTING_LOAD_ATTEMPTS):
            listing_driver = get_driver()
            try:
                detail_urls = get_detail_urls_for_category(listing_driver, cat["url"], max_ads=max_ads_per_category)
            finally:
                listing_driver.quit()
            if detail_urls:
                break
            print(f"  attempt {attempt + 1}/{LISTING_LOAD_ATTEMPTS} found 0 ads, retrying...")

        print(f"  ads found: {len(detail_urls)}")

        for detail_url in detail_urls:
            if detail_url in seen_urls:
                continue
            seen_urls.add(detail_url)

            try:
                job = scrape_detail(detail_url)
                if job:
                    jobs.append(job)
                    print(f"  scraped: {detail_url}")
            except Exception as e:
                print("  skip detail:", detail_url, e)

    return jobs


if __name__ == "__main__":
    jobs = scrape(pages=1)
    print("\nTotal jobs:", len(jobs))
