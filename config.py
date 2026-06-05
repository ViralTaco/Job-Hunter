import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# Project Paths
BASE_DIR = Path(__file__).resolve().parent
SERVICE_ACCOUNT_PATH = BASE_DIR / os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
PROCESSED_JOBS_PATH = BASE_DIR / os.getenv("PROCESSED_JOBS_FILE", "processed_jobs.json")

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Search Settings
TARGET_LOCATIONS: List[str] = ["Belgium"]
TECHNICAL_KEYWORDS: List[str] = [".NET", "C#", "Full-Stack", "C++"]

# Playwright Scraper Settings
SCRAPE_HEADLESS: bool = os.getenv("SCRAPE_HEADLESS", "True").lower() in ("true", "1", "yes")
SCRAPE_TIMEOUT_MS: int = int(os.getenv("SCRAPE_TIMEOUT_MS", "30000"))

# Google Sheets Configuration
GOOGLE_SHEET_NAME: str = os.getenv("GOOGLE_SHEET_NAME", "Belgium Job Search Tracking")
GOOGLE_SHEET_TAB: str = os.getenv("GOOGLE_SHEET_TAB", "Jobs")

# Target Job Board Search Query Configuration
# Pre-defined query structures for popular portals
SEARCH_QUERIES = [
    {
        "name": "ICTJob",
        "base_url": "https://www.ictjob.be/en/search-it-jobs",
        "url_template": "https://www.ictjob.be/en/search-it-jobs?keywords={keyword}&location={location}",
    },
    {
        "name": "Indeed",
        "base_url": "https://be.indeed.com/jobs",
        "url_template": "https://be.indeed.com/jobs?q={keyword}&l={location}",
    }
]


def validate_config() -> None:
    """Verifies that mandatory configuration values are set."""
    warnings = []
    
    if not GEMINI_API_KEY:
        warnings.append(
            "GEMINI_API_KEY is not set. Redaction & cover letter drafting will fail."
        )
        
    if not SERVICE_ACCOUNT_PATH.exists():
        warnings.append(
            f"Google Sheets Service Account key not found at: {SERVICE_ACCOUNT_PATH}. "
            "Sheets sync will be bypassed or run in dry-run mode."
        )
        
    if warnings:
        print("\n--- CONFIGURATION WARNINGS ---")
        for warning in warnings:
            print(f"[!] {warning}")
        print("------------------------------\n")
