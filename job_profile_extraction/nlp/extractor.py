import re
from typing import List
from rapidfuzz import process, fuzz
from job_profile_extraction.models import RawJobAd, JobProfile

TECH_KEYWORDS = [
    'python','java','javascript','typescript','react','next.js','vue','angular','node.js',
    'spring boot','django','flask','fastapi','laravel','php','c#','c++','sql','mysql',
    'postgresql','mongodb','oracle','excel','power bi','tableau','git','docker','kubernetes',
    'aws','azure','linux','html','css','tailwind','figma','selenium','pandas','numpy',
    'tensorflow','pytorch','machine learning','nlp','api','rest api'
]
SKILL_KEYWORDS = [
    'communication','teamwork','leadership','problem solving','analytical','time management',
    'english','khmer','chinese','customer service','negotiation','report writing',
    'project management','data analysis','attention to detail','adaptability'
]
QUALIFICATION_PATTERNS = [
    r'(?i)(bachelor[^\.\n]+)', r'(?i)(master[^\.\n]+)', r'(?i)(degree[^\.\n]+)',
    r'(?i)(certificat\w*[^\.\n]+)', r'(?i)(\d+\+?\s*(?:years|year)[^\.\n]+experience[^\.\n]*)',
    r'(?i)(fresh graduate[^\.\n]*)'
]
RESPONSIBILITY_STARTS = ('responsible', 'manage', 'prepare', 'develop', 'support', 'coordinate',
                         'monitor', 'create', 'maintain', 'analyze', 'report', 'design', 'lead')


def clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text or '').strip()
    return text


def find_keywords(text: str, keywords: List[str]) -> List[str]:
    lower = text.lower()
    found = [kw for kw in keywords if re.search(r'\b' + re.escape(kw.lower()) + r'\b', lower)]
    return sorted(set(found))


def extract_qualifications(text: str) -> List[str]:
    results = []
    for pattern in QUALIFICATION_PATTERNS:
        results.extend([clean_text(m) for m in re.findall(pattern, text)])
    return sorted(set(results))[:10]


def split_sentences(text: str) -> List[str]:
    return [clean_text(s) for s in re.split(r'[\n\.;•\-]+', text) if len(clean_text(s)) > 12]


def extract_responsibilities(text: str) -> List[str]:
    sentences = split_sentences(text)
    res = []
    for s in sentences:
        low = s.lower()
        if low.startswith(RESPONSIBILITY_STARTS) or any(x in low for x in ['responsibilities', 'duties', 'tasks']):
            res.append(s)
    return res[:12]


def normalize_list(items: List[str]) -> List[str]:
    cleaned = []
    for item in items:
        item = clean_text(item).strip(':-,')
        if item and item.lower() not in [x.lower() for x in cleaned]:
            cleaned.append(item)
    return cleaned


def extract_profile(raw: RawJobAd) -> JobProfile:
    full_text = clean_text(' '.join([raw.title, raw.company, raw.location, raw.salary, raw.description]))
    skills = normalize_list(find_keywords(full_text, SKILL_KEYWORDS))
    tech = normalize_list(find_keywords(full_text, TECH_KEYWORDS))
    quals = normalize_list(extract_qualifications(full_text))
    responsibilities = normalize_list(extract_responsibilities(raw.description))

    return JobProfile(
        source=raw.source,
        title=raw.title,
        company=raw.company,
        location=raw.location,
        salary_information=raw.salary,
        deadline=raw.deadline,
        url=raw.url,
        skills=skills,
        technologies=tech,
        qualifications=quals,
        responsibilities=responsibilities,
        raw_text=full_text
    )
