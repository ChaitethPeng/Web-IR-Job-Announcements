from urllib.parse import urljoin
from job_profile_extraction.models import RawJobAd
from job_profile_extraction.scrapers.base import get_soup, text_or_empty

BASE = 'https://mobile.cambojob.com/'


def scrape(pages=1):
    jobs = []
    for page in range(1, pages + 1):
        url = f'{BASE}Jobs/index/page/{page}.htm'
        soup = get_soup(url)
        links = []
        for a in soup.select('a[href*="jobs"], a[href*="share/jobs"]'):
            href = a.get('href', '')
            title = text_or_empty(a)
            if href and title and len(title) > 3:
                links.append((title, urljoin(BASE, href)))
        seen = set()
        for title, detail_url in links[:30]:
            if detail_url in seen:
                continue
            seen.add(detail_url)
            try:
                detail = get_soup(detail_url)
                body = text_or_empty(detail)
                jobs.append(RawJobAd(source='cambojob', title=title, url=detail_url, description=body))
            except Exception as e:
                print('Skip cambojob detail:', detail_url, e)
    return jobs
