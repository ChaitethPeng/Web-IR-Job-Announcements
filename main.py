import argparse
import sys
from collections import Counter
from dataclasses import asdict, fields as dataclass_fields

if hasattr(sys.stdout, "reconfigure"):
    # Job titles/descriptions routinely contain Khmer script; Windows consoles
    # default to a codepage that can't encode it and print() would crash.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from job_profile_extraction.models import RawJobAd
from job_profile_extraction.nlp.extractor import extract_profile
from job_profile_extraction.utils.io import save_csv, save_json, load_json

RAW_JOBS_PATH = "data/raw/jobs_raw.json"
_RAWJOBAD_FIELDS = {f.name for f in dataclass_fields(RawJobAd)}


def dedup_key(row, index, prefix):
    # One ad URL can list several positions (BongThom especially) - each
    # RawJobAd row for that ad shares the same url but has a different
    # title, so keying on url alone would collapse a multi-position ad down
    # to just its last-seen position and silently drop the rest.
    url = row.get("url")
    if not url:
        return f"__no_url_{prefix}_{index}"
    return (url, row.get("title") or f"__no_title_{prefix}_{index}")


def merge_by_url(existing_rows, new_rows):
    """Scraping runs are usually one site at a time (e.g. --site khmer24
    today, --site bongthom yesterday) - merge into what's already on disk
    instead of clobbering it, so the combined dataset accumulates across
    runs. Re-scraping the same ad/position just refreshes its row."""
    merged = {}
    for i, row in enumerate(existing_rows):
        merged[dedup_key(row, i, "existing")] = row
    for i, row in enumerate(new_rows):
        merged[dedup_key(row, i, "new")] = row
    return list(merged.values())


def row_to_rawjobad(row):
    filtered = {k: v for k, v in row.items() if k in _RAWJOBAD_FIELDS}
    return RawJobAd(**filtered)


def run_demo():
    sample = RawJobAd(
        source="demo",
        title="Python Data Analyst",
        company="ABC Company",
        location="Phnom Penh",
        salary="$500-$800/month",
        deadline="2026-07-01",
        url="https://example.com/job/1",
        description="""
        Responsibilities: analyze sales data, prepare reports,
        maintain dashboards, and support management decisions.

        Requirements:
        Bachelor degree in IT, Computer Science, or related field.
        1 year experience in data analysis.

        Skills:
        communication, teamwork, problem solving, English.

        Technologies:
        Python, SQL, Excel, Power BI, pandas.
        """
    )

    profiles = [extract_profile(sample).to_dict()]

    save_csv(profiles, "data/output/job_profiles.csv")
    save_json(profiles, "data/output/job_profiles.json")

    print("Demo complete.")
    print("Output saved to data/output/")


def scrape_site(site_name, pages):
    try:
        if site_name == "cambojob":
            from job_profile_extraction.scrapers.cambojob import scrape

        elif site_name == "bongthom":
            from job_profile_extraction.scrapers.bongthom import scrape

        elif site_name == "camhr":
            from job_profile_extraction.scrapers.camhr import scrape

        elif site_name == "khmer24":
            from job_profile_extraction.scrapers.khmer24 import scrape

        else:
            raise ValueError(f"Unknown site: {site_name}")

        print(f"\nScraping {site_name} ...")

        jobs = scrape(pages=pages)

        print(f"Found {len(jobs)} jobs from {site_name}")

        return jobs

    except Exception as e:
        print(f"ERROR scraping {site_name}: {e}")
        return []


def save_bongthom_category_ranking():
    from job_profile_extraction.scrapers.bongthom import get_category_directory

    print("\nFetching BongThom category directory (site-wide posted-position counts) ...")
    categories = get_category_directory()
    categories.sort(key=lambda c: c["job_count"], reverse=True)

    save_csv(categories, "data/output/bongthom_categories.csv")
    save_json(categories, "data/output/bongthom_categories.json")

    print("Top categories by posted positions (BongThom-wide):")
    for cat in categories[:10]:
        print(f"  {cat['job_count']:>4}  {cat['category']}")

    print("Saved: data/output/bongthom_categories.csv / .json")


def save_scraped_category_ranking(source_name, rows):
    """Unlike BongThom (which publishes its own site-wide category counts),
    CamHR and Khmer24 don't expose per-category totals anywhere - so this
    ranking is tallied from every {source_name} row merged onto disk so far
    (accumulated across runs), not just what this particular run scraped."""
    counter = Counter()
    for row in rows:
        for cat in row.get("career_categories") or []:
            if cat:
                counter[cat] += 1

    if not counter:
        return

    ranking = [{"category": cat, "job_count": count} for cat, count in counter.most_common()]

    save_csv(ranking, f"data/output/{source_name}_categories.csv")
    save_json(ranking, f"data/output/{source_name}_categories.json")

    print(f"\nTop categories among scraped {source_name} postings (accumulated across runs, not site-wide):")
    for row in ranking[:10]:
        print(f"  {row['job_count']:>4}  {row['category']}")

    print(f"Saved: data/output/{source_name}_categories.csv / .json")


def run_scrape(site, pages):
    raw_jobs = []
    sites = ["camhr", "bongthom", "cambojob", "khmer24"] if site == "all" else [site]

    for s in sites:
        raw_jobs.extend(scrape_site(s, pages))

    print(f"\nTotal new jobs scraped this run: {len(raw_jobs)}")

    if len(raw_jobs) == 0:
        print("No jobs found this run - existing data/ files are left untouched.")
        return

    print("\nSample jobs:")

    for i, job in enumerate(raw_jobs[:5]):
        print(f"{i+1}. {job.title}")

    new_rows = [asdict(job) for job in raw_jobs]
    existing_rows = load_json(RAW_JOBS_PATH)
    raw_rows = merge_by_url(existing_rows, new_rows)

    added_or_updated = len(raw_rows) - len(existing_rows)
    if existing_rows:
        print(f"\nMerged with {len(existing_rows)} existing row(s) already on disk "
              f"({added_or_updated} new, {len(new_rows) - max(added_or_updated, 0)} refreshed)")

    if "bongthom" in sites:
        try:
            save_bongthom_category_ranking()
        except Exception as e:
            print(f"Could not fetch BongThom category ranking: {e}")

    for s in ("camhr", "khmer24"):
        if s in sites:
            save_scraped_category_ranking(s, [row for row in raw_rows if row.get("source") == s])

    profiles = []

    for row in raw_rows:
        try:
            profiles.append(extract_profile(row_to_rawjobad(row)).to_dict())
        except Exception as e:
            print(f"Extraction failed: {e}")

    save_csv(raw_rows, "data/raw/jobs_raw.csv")
    save_json(raw_rows, RAW_JOBS_PATH)

    save_csv(profiles, "data/output/job_profiles.csv")
    save_json(profiles, "data/output/job_profiles.json")

    print("\nCompleted Successfully")
    print(f"Raw Jobs     : {len(raw_rows)} (total on disk, across all sites/runs)")
    print(f"Job Profiles : {len(profiles)}")

    print("\nFiles Generated:")
    print("data/raw/jobs_raw.csv")
    print("data/raw/jobs_raw.json")
    print("data/output/job_profiles.csv")
    print("data/output/job_profiles.json")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Job Profile Extraction Pipeline"
    )

    parser.add_argument(
        "--mode",
        choices=["demo", "scrape"],
        default="demo"
    )

    parser.add_argument(
        "--site",
        choices=["camhr", "bongthom", "cambojob", "khmer24", "all"],
        default="all"
    )

    parser.add_argument(
        "--pages",
        type=int,
        default=1
    )

    args = parser.parse_args()

    if args.mode == "demo":
        run_demo()

    else:
        run_scrape(args.site, args.pages)