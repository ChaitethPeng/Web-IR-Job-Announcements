from job_profile_extraction.models import RawJobAd
from job_profile_extraction.scrapers.base import text_or_empty
from playwright.sync_api import sync_playwright

BASE = 'https://www.camhr.com/'


def scrape(pages=1):
    jobs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE, wait_until='networkidle', timeout=60000)
        # Generic link discovery because CamHR is dynamic and selectors can change.
        anchors = page.locator('a').all()[:200]
        links = []
        for a in anchors:
            try:
                href = a.get_attribute('href') or ''
                text = a.inner_text(timeout=1000).strip()
                if href and text and ('job' in href.lower() or 'jobs' in href.lower()):
                    links.append((text, href if href.startswith('http') else BASE.rstrip('/') + '/' + href.lstrip('/')))
            except Exception:
                pass
        for title, url in links[:30 * pages]:
            try:
                page.goto(url, wait_until='networkidle', timeout=60000)
                body = page.locator('body').inner_text(timeout=5000)
                jobs.append(RawJobAd(source='camhr', title=title, url=url, description=body))
            except Exception as e:
                print('Skip camhr detail:', url, e)
        browser.close()
    return jobs
