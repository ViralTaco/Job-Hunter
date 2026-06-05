import os
import json
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

# Load Search Configuration from JSON
CONFIG_JSON_PATH = BASE_DIR / "search_config.json"
_config_data = {}

if CONFIG_JSON_PATH.exists():
    try:
        with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
            _config_data = json.load(f)
    except Exception as e:
        print(f"[!] Error reading search_config.json: {e}")

# Search Settings
TARGET_LOCATIONS: List[str] = _config_data.get("locations")
TECHNICAL_KEYWORDS: List[str] = _config_data.get("keywords")

# Playwright Scraper Settings
SCRAPE_HEADLESS: bool = os.getenv("SCRAPE_HEADLESS", "True").lower() in ("true", "1", "yes")
SCRAPE_TIMEOUT_MS: int = int(os.getenv("SCRAPE_TIMEOUT_MS", "30000"))

# Google Sheets Configuration
GOOGLE_SHEET_NAME: str = _config_data.get("sheet_name")
GOOGLE_SHEET_TAB: str = _config_data.get("sheet_tab")

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
    },
    {
        "name": "Forem",
        "base_url": "https://www.leforem.be/recherche-offres-emploi",
        "url_template": "https://www.leforem.be/recherche-offres-emploi/resultats?motsCles={keyword}",
    },
    {
        "name": "Randstad",
        "base_url": "https://www.randstad.be/nl/vacatures",
        "url_template": "https://www.randstad.be/nl/vacatures/?q={keyword}&l={location}",
    },
    {
        "name": "Adecco",
        "base_url": "https://www.adecco.be/nl-be/vacatures",
        "url_template": "https://www.adecco.be/nl-be/vacatures?k={keyword}&l={location}",
    },
    {
        "name": "Manpower",
        "base_url": "https://www.manpower.be/en/jobs",
        "url_template": "https://www.manpower.be/en/jobs?search={keyword}&location={location}",
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
