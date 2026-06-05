import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

import config
from scraper.playwright_scraper import PlaywrightScraper
from pipeline.normalizer import DataPipeline
from sheets.integration import GoogleSheetsConnector, DryRunSheetsConnector
from drafting.engine import DraftingEngine, MockDraftingEngine


def load_resume_text(resume_path_str: str) -> Optional[str]:
    """Attempts to load the resume from the specified file path."""
    path = Path(resume_path_str)
    if not path.exists():
        print(f"[!] Resume file not found at: {path.resolve()}")
        print("[!] Drafting features will be skipped. Only scraping and sheet logging will run.")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read().strip()
            if not text:
                print("[!] Warning: Resume file is empty.")
                return None
            print(f"[*] Successfully loaded resume from {path.name} ({len(text)} characters).")
            return text
    except Exception as e:
        print(f"[!] Error reading resume file: {e}")
        return None


def run_pipeline(
    resume_path: str,
    dry_run: bool = False,
    search_only: bool = False,
    limit: int = 10
) -> None:
    """
    Orchestrates the job hunter automation pipeline.
    """
    print("==================================================")
    print("      BELGIUM JOB HUNTER AUTOMATION ENGINE        ")
    print("==================================================")

    # 1. Configuration Validation
    config.validate_config()

    # Determine if we need to force dry-run due to missing credentials
    use_dry_run_sheets = dry_run or not config.SERVICE_ACCOUNT_PATH.exists()
    use_mock_drafting = dry_run or not config.GEMINI_API_KEY or search_only

    if use_dry_run_sheets:
        print("[*] Sheets Integration: Running in DRY-RUN mode.")
    else:
        print("[*] Sheets Integration: Running in ACTIVE PRODUCTION mode.")

    if use_mock_drafting:
        if search_only:
            print("[*] Drafting Engine: DISABLED (search-only flag set).")
        else:
            print("[*] Drafting Engine: Running in MOCK/SIMULATION mode.")
    else:
        print("[*] Drafting Engine: Running in ACTIVE Gemini AI mode.")

    # 2. Load Resume
    resume_text: Optional[str] = None
    if not search_only:
        resume_text = load_resume_text(resume_path)

    # 3. Scraping Phase
    raw_listings: List[Dict[str, Any]] = []
    scraper = PlaywrightScraper(headless=config.SCRAPE_HEADLESS, timeout_ms=config.SCRAPE_TIMEOUT_MS)

    for keyword in config.TECHNICAL_KEYWORDS:
        for location in config.TARGET_LOCATIONS:
            try:
                listings = scraper.scrape_jobs(keyword=keyword, location=location)
                raw_listings.extend(listings)
            except Exception as e:
                print(f"[!] Scraping failed for keyword '{keyword}' in '{location}': {e}")
                continue

    if not raw_listings:
        print("[*] No listings returned by the scraper. Exiting.")
        return

    # 4. Data Pipeline: Validation & Deduplication
    pipeline = DataPipeline(cache_file_path=config.PROCESSED_JOBS_PATH)
    normalized_listings = pipeline.normalize_and_validate(raw_listings)
    new_listings = pipeline.deduplicate(normalized_listings)

    if not new_listings:
        print("[*] All scraped listings were duplicates. No new jobs to process.")
        return

    # Limit the number of jobs processed in a single run (avoids API rate limits)
    processing_batch = new_listings[:limit]
    print(f"[*] Processing {len(processing_batch)} new listings out of {len(new_listings)} scraped (limit: {limit}).")

    # 5. Initialize Connectors
    sheets_connector = (
        DryRunSheetsConnector(config.SERVICE_ACCOUNT_PATH, config.GOOGLE_SHEET_NAME, config.GOOGLE_SHEET_TAB)
        if use_dry_run_sheets
        else GoogleSheetsConnector(config.SERVICE_ACCOUNT_PATH, config.GOOGLE_SHEET_NAME, config.GOOGLE_SHEET_TAB)
    )

    draft_engine = (
        MockDraftingEngine() 
        if use_mock_drafting or not resume_text
        else DraftingEngine()
    )

    try:
        sheets_connector.connect()
    except Exception as e:
        print(f"[!] Critical error connecting to Google Sheets: {e}")
        print("[*] Falling back to Dry-Run logging for this execution session.")
        sheets_connector = DryRunSheetsConnector(
            config.SERVICE_ACCOUNT_PATH, 
            config.GOOGLE_SHEET_NAME, 
            config.GOOGLE_SHEET_TAB
        )

    # 6. Drafting & Export Phase
    for index, job in enumerate(processing_batch, 1):
        print(f"\n--- [{index}/{len(processing_batch)}] Processing: {job.job_title} at {job.company} ---")
        
        status = "Scraped"
        cover_letter = ""

        if resume_text and not search_only:
            try:
                # A. Redact Resume
                redacted_resume = draft_engine.redact_resume(resume_text)
                
                # B. Generate cover letter
                cover_letter = draft_engine.generate_cover_letter(
                    clean_resume=redacted_resume, 
                    job_description=job.description
                )
                status = "Drafted"
                print("[*] Tailored cover letter drafted.")
            except Exception as draft_err:
                print(f"[!] Cover letter drafting failed: {draft_err}")
                status = "Scraping Succeeded (Drafting Failed)"

        # C. Write to sheet
        try:
            sheets_connector.append_job(job, status=status, cover_letter=cover_letter)
        except Exception as sheet_err:
            print(f"[!] Error writing job to sheets: {sheet_err}")

    print("\n==================================================")
    print("      JOB SEARCH PIPELINE WORKFLOW COMPLETE       ")
    print("==================================================")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Automate job search crawling, validation, PII redaction, and cover letter drafting."
    )
    parser.add_argument(
        "--resume",
        type=str,
        default="resume.txt",
        help="Path to the resume text file to redact and use for cover letters (default: resume.txt)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Runs scraper and prints actions without connecting to Google Sheets or calling live Gemini endpoints."
    )
    parser.add_argument(
        "--search-only",
        action="store_true",
        help="Crawls jobs and logs to spreadsheet only. Skips cover letter generation completely."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of new job listings to process cover letters for in this run (default: 10)."
    )
    
    args = parser.parse_args()
    
    try:
        run_pipeline(
            resume_path=args.resume,
            dry_run=args.dry_run,
            search_only=args.search_only,
            limit=args.limit
        )
    except KeyboardInterrupt:
        print("\n[!] Execution interrupted by user. Exiting.")
        sys.exit(0)
