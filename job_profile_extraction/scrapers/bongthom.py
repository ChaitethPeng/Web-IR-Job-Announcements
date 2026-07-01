import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import re
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from job_profile_extraction.models import RawJobAd
from job_profile_extraction.scrapers.base import get_soup, text_or_empty

BASE = "https://www.bongthom.com/"

# BongThom's category listing shows ~40 ads per page; this is a safety cap on
# how many pages we'll page through for a single category (largest category
# observed has ~130 positions / ~80 ads, i.e. 2 pages).
MAX_PAGES_PER_CATEGORY = 8


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--user-agent=Mozilla/5.0")

    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )


def get_category_directory(driver=None):
    """Read the Career Category sidebar (present on every category page) to get
    every category's id, name and BongThom's own posted-position count. This
    count is the authoritative "market demand" ranking - it reflects the whole
    site, not just what we've scraped."""
    owns_driver = driver is None
    if owns_driver:
        driver = get_driver()

    try:
        driver.get(urljoin(BASE, "job_category.html"))
        time.sleep(4)
        soup = BeautifulSoup(driver.page_source, "html.parser")

        categories = []
        seen_ids = set()

        for a in soup.select('a[href*="job_category-"]'):
            href = a["href"]
            match = re.search(r"job_category-(\d+)\.html", href)
            if not match:
                continue

            category_id = match.group(1)
            if category_id in seen_ids:
                continue

            badge = a.select_one("span.badge")
            if not badge:
                continue

            count_text = clean_text(badge.get_text())
            try:
                job_count = int(count_text)
            except ValueError:
                continue

            name = clean_text(a.get_text()).replace(count_text, "", 1).strip()
            if not name:
                continue

            seen_ids.add(category_id)
            categories.append({
                "category_id": category_id,
                "category": name,
                "job_count": job_count,
                "url": urljoin(BASE, f"job_category-{category_id}.html"),
            })

        return categories

    finally:
        if owns_driver:
            driver.quit()


def get_detail_urls_for_category(driver, category_url, max_pages=MAX_PAGES_PER_CATEGORY):
    """Page through a category listing (?page=2, ?page=3, ...) until a page
    comes back with no new job_detail links, collecting unique ad URLs."""
    detail_urls = []
    seen = set()

    for page in range(1, max_pages + 1):
        page_url = category_url if page == 1 else f"{category_url}?page={page}"
        driver.get(page_url)
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        new_links = []

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "job_detail" in href:
                full_url = urljoin(BASE, href)
                if full_url not in seen:
                    seen.add(full_url)
                    new_links.append(full_url)

        if not new_links:
            break

        detail_urls.extend(new_links)

    return detail_urls


def remove_noselect(soup):
    for span in soup.select(".noselect"):
        span.decompose()


def extract_company(soup):
    company = soup.select_one("a.sub-title")
    if company:
        return clean_text(company.get_text()).replace("with ", "")
    return ""


def extract_deadline(soup):
    time_el = soup.select_one("time[datetime]")
    if time_el and time_el.get("datetime"):
        return time_el["datetime"].strip()
    if time_el:
        return clean_text(time_el.get_text())
    return ""


def extract_company_description(soup):
    """The free-text company/announcement blurb shown above the position list."""
    detail_block = soup.select_one("#job-detail")
    if not detail_block:
        return ""
    editor = detail_block.find("div", class_="ql-editor")
    return clean_text(editor.get_text(" ")) if editor else ""


def extract_key_value_pairs(container):
    """Workplace/Position Circumstances render as:
    <ul class="key-list"><li><strong>Label:</strong><span class="value">...</span></li></ul>
    Covers Environment, (workplace) Languages, Location, Career Category, Schedule, Salary.
    """
    pairs = {}
    for li in container.select("ul.key-list > li"):
        strong = li.find("strong")
        value_el = li.select_one("span.value")
        if not strong or not value_el:
            continue
        label = clean_text(strong.get_text()).rstrip(":").lower()
        pairs[label] = clean_text(value_el.get_text())
    return pairs


def extract_labeled_lists(container):
    """Duties & Responsibilities / Benefits / Expected Profile sections render as:
    <div class="clearfix en"><strong>Label:</strong></div><ul class="job-detail-req"><li>...</li></ul>
    """
    result = {}
    for label_div in container.select("div.clearfix.en"):
        strong = label_div.find("strong")
        if not strong:
            continue
        label = clean_text(strong.get_text()).rstrip(":")
        if not label:
            continue
        ul = label_div.find_next_sibling("ul", class_="job-detail-req")
        items = []
        if ul:
            for li in ul.find_all("li", recursive=False):
                item_text = clean_text(li.get_text(" "))
                if item_text:
                    items.append(item_text)
        result[label] = items
    return result


def extract_position_summary(position_block):
    for strong in position_block.select("strong.duty-req"):
        if "position summary" in clean_text(strong.get_text()).lower():
            editor = strong.find_next_sibling("div", class_="ql-editor")
            if editor:
                return clean_text(editor.get_text(" "))
    return ""


def build_job_ad(title, company, deadline, url, container, description, position_summary):
    pairs = extract_key_value_pairs(container)
    lists = extract_labeled_lists(container)

    career_categories = [
        c.strip() for c in pairs.get("career category", "").split(",") if c.strip()
    ]

    return RawJobAd(
        source="bongthom",
        title=title,
        company=company,
        location=pairs.get("location", ""),
        salary=pairs.get("salary", ""),
        deadline=deadline,
        url=url,
        description=description,
        career_categories=career_categories,
        environment=pairs.get("environment", ""),
        workplace_languages=pairs.get("languages", ""),
        schedule=pairs.get("schedule", ""),
        position_summary=position_summary,
        responsibilities=lists.get("Duties & Responsibilities", []),
        benefits=lists.get("Benefits", []),
        languages_required=lists.get("Languages", []),
        qualifications_required=lists.get("Qualifications", []),
        work_history=lists.get("Work History", []),
        general_technical_skills=lists.get("General & Technical Skills", []),
        soft_skills=lists.get("Soft Skills", []),
    )


def scrape_detail(detail_url):
    soup = get_soup(detail_url)
    remove_noselect(soup)

    title_el = soup.select_one("h1.title")
    main_title = clean_text(title_el.get_text()) if title_el else "Job Detail"

    company = extract_company(soup)
    deadline = extract_deadline(soup)
    company_description = extract_company_description(soup)

    jobs = []
    position_headers = soup.select('h3[id^="position-"]')

    if not position_headers:
        detail_block = soup.select_one("#job-detail")
        description = clean_text(detail_block.get_text(" ")) if detail_block else text_or_empty(soup)
        container = detail_block if detail_block else soup

        jobs.append(build_job_ad(
            title=main_title,
            company=company,
            deadline=deadline,
            url=detail_url,
            container=container,
            description=description,
            position_summary=company_description,
        ))
        return jobs

    for header in position_headers:
        position_title = clean_text(header.get_text())
        position_id = header.get("id", "").replace("position-", "")
        position_block = soup.select_one(f"#job-detail-pos-{position_id}")

        if not position_block:
            continue

        description = clean_text(position_block.get_text(" "))
        position_summary = extract_position_summary(position_block)

        jobs.append(build_job_ad(
            title=position_title,
            company=company,
            deadline=deadline,
            url=detail_url,
            container=position_block,
            description=description,
            position_summary=position_summary,
        ))

    return jobs


def scrape(pages=None):
    """pages limits how many categories to process (falsy/0/None = all
    categories). Each category is paged through fully via get_detail_urls_for_category."""
    jobs = []
    seen_details = set()

    driver = get_driver()

    try:
        categories = get_category_directory(driver)
        total_listed = sum(c["job_count"] for c in categories)
        print(f"BongThom: {len(categories)} categories found, {total_listed} positions listed site-wide")

        if pages:
            categories = categories[:pages]

        for cat in categories:
            print(f"Category: {cat['category']} (listed positions: {cat['job_count']})")

            detail_urls = get_detail_urls_for_category(driver, cat["url"])
            print(f"  ads found: {len(detail_urls)}")

            for detail_url in detail_urls:
                if detail_url in seen_details:
                    continue

                seen_details.add(detail_url)

                try:
                    detail_jobs = scrape_detail(detail_url)
                    jobs.extend(detail_jobs)
                    print(f"  scraped {len(detail_jobs)} position(s): {detail_url}")
                    time.sleep(0.5)

                except Exception as e:
                    print("  skip detail:", detail_url, e)

    finally:
        driver.quit()

    return jobs


if __name__ == "__main__":
    jobs = scrape(pages=2)
    print("\nTotal jobs:", len(jobs))
