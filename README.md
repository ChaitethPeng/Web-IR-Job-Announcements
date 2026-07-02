# Job Profile Extraction Project

End-to-end Python project for scraping job ads and extracting structured job profiles.

Websites prepared:
- CamHR: https://www.camhr.com/ (public JSON API, no browser needed - fast)
- BongThom: https://www.bongthom.com/ (category listings are JS-rendered, detail pages are plain HTML)
- Khmer24: https://www.khmer24.com/ (Cloudflare-protected classifieds site - see notes below)
- CamboJob mobile: https://mobile.cambojob.com/

> Use this project for study/research. Always check each website's Terms of Service and robots.txt before scraping. Use low speed and do not overload servers.

## Setup
```bash
python -m venv .venv
.venv\Scripts\activate     # Windows
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

BongThom and Khmer24 use Selenium + `webdriver-manager` (downloads a matching
ChromeDriver automatically the first time you run them) - a local Chrome/
Chromium install is required. CamHR needs neither; it talks to CamHR's own
JSON API directly.

## Run demo extraction from sample text
```bash
python main.py --mode demo
```

## Scrape and extract
```bash
python main.py --mode scrape --site camhr --pages 1
python main.py --mode scrape --site bongthom --pages 1
python main.py --mode scrape --site khmer24 --pages 1
python main.py --mode scrape --site cambojob --pages 2
```

`--pages` means something different per site:
- **CamHR** - number of size-100 listing pages to sweep (`--pages 1` = up to
  100 jobs; `--pages 0` = every job on the site, ~1500 jobs / ~16 requests).
  Pure JSON API calls, no browser - a full run only takes a few minutes.
- **BongThom** - number of career categories to process (`--pages 0` = all
  ~95 categories, ~1000 posted positions). Each category is paged through in
  full internally, so even `--pages 1` returns every ad in that one
  category, not just the first page.
- **Khmer24** - number of job categories to process (`--pages 0` = all ~35).
  Capped by design (see below) - even `--pages 0` only pulls
  `MAX_ADS_PER_CATEGORY` (15 by default) ads per category, not everything.

### Khmer24 is slow by necessity
Every khmer24 page sits behind a Cloudflare JS challenge. A fresh headless
browser session passes it once, but a *second* page load in that same
session reliably gets stuck on "Just a moment..." forever - so every job
detail page needs its own freshly-launched browser, which costs ~10-15
seconds each (and Cloudflare's challenge is flaky enough that this can take
a couple of retries). `job_profile_extraction/scrapers/khmer24.py` caps ads
per category (`MAX_ADS_PER_CATEGORY`) to keep a default run to a sample-sized
few minutes rather than many hours. Raise that constant (and/or `--pages`)
if you want a bigger sweep, but budget the runtime accordingly.

## Output files
- `data/raw/jobs_raw.csv` / `.json` - every scraped job posting/position,
  across whichever sites you ran. Structured columns (populated where the
  source site exposes them; empty otherwise): `career_categories`,
  `industry`, `environment`, `workplace_languages`, `schedule`,
  `position_summary`, `responsibilities`, `benefits`, `languages_required`,
  `qualifications_required`, `work_history`, `general_technical_skills`,
  `soft_skills` (list columns are `; `-joined in the CSV).
- `data/output/job_profiles.csv` / `.json` - keyword-based skill/tech/
  qualification extraction over the free-text description (all sources) -
  most useful for CamHR/Khmer24 rows, since their job ads are unstructured
  text rather than templated fields like BongThom's.
- `data/output/bongthom_categories.csv` / `.json` - every BongThom career
  category with its **site-wide** posted-position count (read straight from
  BongThom's own category sidebar) - the "which category has the most
  demand" ranking.
- `data/output/camhr_categories.csv` / `.json` and
  `data/output/khmer24_categories.csv` / `.json` - category counts tallied
  from **what was actually scraped this run**, not a site-wide total (neither
  site publishes one). Re-run with a higher `--pages` for a more complete
  picture.

## Web UI (job explorer)
A Flask app (`app.py`) serves a dashboard for browsing the scraped dataset:
search box, category/source/location/salary filters, a job card grid, and a
detail panel (title, company, location, salary, deadline, source, skills,
technologies, qualifications, responsibilities, benefits, full description,
and an "Open Original Announcement" link). Supports Khmer and English text.

```bash
python app.py
```
Then open http://127.0.0.1:5000/. It reads directly from
`data/raw/jobs_raw.json` and `data/output/job_profiles.json`, so re-run a
scrape (see above) and refresh the page to see new data - no restart needed.

API endpoints, if you want to query the data directly:
- `GET /api/jobs?q=...&category=...&source=...&location=...` - filtered job list
- `GET /api/meta` - facet values (sources, locations, category counts) and header stats
