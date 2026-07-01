import time
import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; AcademicJobResearchBot/1.0; +contact: student-project)'
}


def get_soup(url: str, delay: float = 1.5) -> BeautifulSoup:
    time.sleep(delay)
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return BeautifulSoup(r.text, 'lxml')


def text_or_empty(node):
    return node.get_text(' ', strip=True) if node else ''
