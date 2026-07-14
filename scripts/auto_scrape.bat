@echo off
REM Runs every 3 days via Windows Task Scheduler (task name: JobScraperAutoRun).
REM Scrapes all 4 sites and merges results into data/raw + data/output, same
REM as running main.py by hand. --pages 5 keeps each run to roughly 30-60
REM minutes total (BongThom: 5 categories, CamHR: 500 jobs, Khmer24: 5
REM categories x 15 ads capped, CamboJob: 5 city listings) instead of the
REM multi-hour full-site sweep --pages 0 would take on some sites.
REM Edit PAGES below, or run main.py manually with --pages 0 for a full sweep.

setlocal
set PROJECT_DIR=D:\Master_ITC\study\Year 1\IR\job_profile_extraction_project
set PAGES=5
set LOG_FILE=%PROJECT_DIR%\logs\auto_scrape.log

cd /d "%PROJECT_DIR%"

echo. >> "%LOG_FILE%"
echo ==== Run started %date% %time% ==== >> "%LOG_FILE%"
python main.py --mode scrape --site all --pages %PAGES% >> "%LOG_FILE%" 2>&1
echo ==== Run finished %date% %time% ==== >> "%LOG_FILE%"
