# Job Profile Extraction Project

End-to-end Python project for scraping job ads and extracting structured job profiles.

Websites prepared:
- CamHR: https://www.camhr.com/
- BongThom: https://www.bongthom.com/
- CamboJob mobile: https://mobile.cambojob.com/

> Use this project for study/research. Always check each website's Terms of Service and robots.txt before scraping. Use low speed and do not overload servers.

## Setup
```bash
python -m venv .venv
.venv\Scripts\activate     # Windows
pip install -r requirements.txt
python -m spacy download en_core_web_sm
playwright install chromium
```

## Run demo extraction from sample text
```bash
python main.py --mode demo
```

## Scrape and extract
```bash
python main.py --mode scrape --site cambojob --pages 2
python main.py --mode scrape --site bongthom --pages 2
python main.py --mode scrape --site camhr --pages 2
```

For BongThom, `--pages` limits how many career categories are processed
(pass `--pages 0` to scrape every category on the site - there are ~95,
totalling ~1000 posted positions, so a full run takes a while and makes a
lot of requests). Every category is paged through in full internally, so
even `--pages 1` returns every ad in that one category, not just the first
page of results.

Output files:
- `data/raw/jobs_raw.csv` / `.json` - every scraped job posting/position.
  For BongThom this includes structured columns: `career_categories`,
  `environment`, `workplace_languages`, `schedule`, `position_summary`,
  `responsibilities`, `benefits`, `languages_required`,
  `qualifications_required`, `work_history`, `general_technical_skills`,
  `soft_skills` (list columns are `; `-joined in the CSV).
- `data/output/job_profiles.csv` / `.json` - keyword-based skill/tech/
  qualification extraction (all sources).
- `data/output/bongthom_categories.csv` / `.json` - every BongThom career
  category with its site-wide posted-position count, sorted descending -
  this is the "which category has the most demand" ranking.
