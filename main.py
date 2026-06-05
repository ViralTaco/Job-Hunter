import argparse
import sys
import os
import threading
import builtins
from concurrent.futures import ThreadPoolExecutor
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

    # 3. Initialize Shared Pipeline, Connectors & Locks
    pipeline = DataPipeline(cache_file_path=config.PROCESSED_JOBS_PATH)
    
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

    # Scraper instance is thread-safe as it launches browser contexts per thread
    scraper = PlaywrightScraper(headless=config.SCRAPE_HEADLESS, timeout_ms=config.SCRAPE_TIMEOUT_MS)
    
    # Thread locks for shared resources
    locks = {
        "pipeline": threading.Lock(),
        "sheets": threading.Lock(),
        "counter": threading.Lock()
    }
    
    shared_state = {
        "processed_count": 0
    }

    # Prepare tasks list
    tasks = []
    for keyword in config.TECHNICAL_KEYWORDS:
        for location in config.TARGET_LOCATIONS:
            tasks.append((keyword, location))

    # Overwrite builtins.print to prevent console clutter during progress updates
    _original_print = builtins.print
    
    try:
        with open("job_hunter.log", "w", encoding="utf-8") as f:
            f.write("=== Job Hunter Execution Log ===\n")
    except Exception:
        pass

    def redirect_print_to_file(*args, **kwargs):
        try:
            with open("job_hunter.log", "a", encoding="utf-8") as f:
                f.write(" ".join(map(str, args)) + "\n")
        except Exception:
            pass

    # Redirect prints
    builtins.print = redirect_print_to_file

    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

    _original_print(f"[*] Starting {len(tasks)} queries in parallel threads. Rendering dashboard...")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
    ) as progress:

        # Limit thread count to core count - 1
        cpu_cores = os.cpu_count()
        max_workers = max(1, (cpu_cores - 1) if cpu_cores else 3)

        def process_task(keyword: str, location: str, task_id) -> None:
            """Worker task to process a single keyword and location combination."""
            # 1. Check limit before starting work
            with locks["counter"]:
                if shared_state["processed_count"] >= limit:
                    progress.update(task_id, description=f"[{keyword}@{location}] Stopped (Limit reached)", completed=100)
                    return

            progress.update(task_id, description=f"[{keyword}@{location}] Initializing browser...", completed=10)

            try:
                listings = scraper.scrape_jobs(keyword=keyword, location=location)
                progress.update(task_id, description=f"[{keyword}@{location}] Scraped ({len(listings)} found)", completed=50)
                if not listings:
                    progress.update(task_id, description=f"[{keyword}@{location}] Finished (0 found)", completed=100)
                    return
                
                # 2. Validate & Deduplicate (locked to prevent cache corruption)
                progress.update(task_id, description=f"[{keyword}@{location}] Filtering duplicates...", completed=60)
                with locks["pipeline"]:
                    normalized_listings = pipeline.normalize_and_validate(listings)
                    new_listings = pipeline.deduplicate(normalized_listings)
                
                if not new_listings:
                    progress.update(task_id, description=f"[{keyword}@{location}] Finished (duplicates)", completed=100)
                    return
                
                progress.update(task_id, description=f"[{keyword}@{location}] Processing {len(new_listings)} new jobs", completed=70)

                # 3. Process each listing
                for job in new_listings:
                    with locks["counter"]:
                        if shared_state["processed_count"] >= limit:
                            progress.update(task_id, description=f"[{keyword}@{location}] Stopped (Limit reached)", completed=100)
                            return
                        shared_state["processed_count"] += 1
                        local_idx = shared_state["processed_count"]
                    
                    status = "Scraped"
                    cover_letter = ""

                    if resume_text and not search_only:
                        progress.update(task_id, description=f"[{keyword}@{location}] Drafting: {job.job_title[:20]}...", completed=80)
                        try:
                            # Redaction and drafting run concurrently without locks
                            redacted_resume = draft_engine.redact_resume(resume_text)
                            cover_letter = draft_engine.generate_cover_letter(
                                clean_resume=redacted_resume, 
                                job_description=job.description
                            )
                            status = "Drafted"
                        except Exception:
                            status = "Scraping Succeeded (Drafting Failed)"

                    # 4. Write to Google Sheet (locked to prevent concurrent write collisions)
                    progress.update(task_id, description=f"[{keyword}@{location}] Appending to Sheet...", completed=90)
                    with locks["sheets"]:
                        try:
                            sheets_connector.append_job(job, status=status, cover_letter=cover_letter)
                        except Exception:
                            pass
                
                progress.update(task_id, description=f"[{keyword}@{location}] Completed!", completed=100)
                            
            except Exception as e:
                progress.update(task_id, description=f"[{keyword}@{location}] Failed: {str(e)[:25]}", completed=100)

        # Create tasks on progress and submit to executor
        futures = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for keyword, location in tasks:
                # Add task to progress dashboard
                task_id = progress.add_task(
                    description=f"[{keyword}@{location}] Pending...", 
                    total=100
                )
                futures.append(executor.submit(process_task, keyword, location, task_id))
            
            # Wait for all threads to finish
            for fut in futures:
                try:
                    fut.result()
                except Exception:
                    pass

    # Restore original print function
    builtins.print = _original_print

    print("\n==================================================")
    print(f"      JOB SEARCH PIPELINE WORKFLOW COMPLETE       ")
    print(f"      Processed & logged: {shared_state['processed_count']} jobs  ")
    print("      (Detailed log written to: job_hunter.log)   ")
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
