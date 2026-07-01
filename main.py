import argparse
from dataclasses import asdict

from job_profile_extraction.models import RawJobAd
from job_profile_extraction.nlp.extractor import extract_profile
from job_profile_extraction.utils.io import save_csv, save_json


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


def run_scrape(site, pages):
    raw_jobs = []
    sites = ["camhr", "bongthom", "cambojob"] if site == "all" else [site]

    for s in sites:
        raw_jobs.extend(scrape_site(s, pages))

    if "bongthom" in sites:
        try:
            save_bongthom_category_ranking()
        except Exception as e:
            print(f"Could not fetch BongThom category ranking: {e}")

    print(f"\nTotal jobs collected: {len(raw_jobs)}")

    if len(raw_jobs) == 0:
        print("No jobs found.")
        return

    print("\nSample jobs:")

    for i, job in enumerate(raw_jobs[:5]):
        print(f"{i+1}. {job.title}")

    raw_rows = [asdict(job) for job in raw_jobs]

    profiles = []

    for job in raw_jobs:
        try:
            profiles.append(extract_profile(job).to_dict())
        except Exception as e:
            print(f"Extraction failed: {e}")

    save_csv(raw_rows, "data/raw/jobs_raw.csv")
    save_json(raw_rows, "data/raw/jobs_raw.json")

    save_csv(profiles, "data/output/job_profiles.csv")
    save_json(profiles, "data/output/job_profiles.json")

    print("\nCompleted Successfully")
    print(f"Raw Jobs     : {len(raw_rows)}")
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
        choices=["camhr", "bongthom", "cambojob", "all"],
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