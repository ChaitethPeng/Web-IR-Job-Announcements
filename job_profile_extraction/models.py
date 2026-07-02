from dataclasses import dataclass, asdict, field
from typing import List, Optional

@dataclass
class RawJobAd:
    source: str
    title: str
    company: str = ""
    location: str = ""
    salary: str = ""
    deadline: str = ""
    url: str = ""
    description: str = ""
    # Structured fields populated by scrapers that expose them on-page (e.g. BongThom).
    # Left at their defaults for sources that only provide free-text descriptions.
    career_categories: List[str] = field(default_factory=list)
    industry: str = ""
    environment: str = ""
    workplace_languages: str = ""
    schedule: str = ""
    position_summary: str = ""
    responsibilities: List[str] = field(default_factory=list)
    benefits: List[str] = field(default_factory=list)
    languages_required: List[str] = field(default_factory=list)
    qualifications_required: List[str] = field(default_factory=list)
    work_history: List[str] = field(default_factory=list)
    general_technical_skills: List[str] = field(default_factory=list)
    soft_skills: List[str] = field(default_factory=list)

@dataclass
class JobProfile:
    source: str
    title: str
    company: str
    location: str
    salary_information: str
    deadline: str
    url: str
    skills: List[str]
    technologies: List[str]
    qualifications: List[str]
    responsibilities: List[str]
    raw_text: str

    def to_dict(self):
        return asdict(self)
