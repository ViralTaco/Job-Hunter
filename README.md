# Belgium Job Search Automation System

A modular, robust, and maintainable Python-based automation pipeline to assist a Junior Full-Stack .NET Developer in finding job listings in Belgium, logging them to a Google Sheet, and drafting tailored cover letters using Gemini AI while protecting personal data.

## Project Structure

```text
Job Hunter/
├── .gitignore
├── requirements.txt
├── README.md
├── config.py              # Centralized environment and query configuration
├── main.py                # Command-line entrypoint and orchestrator
├── scraper/
│   ├── __init__.py
│   ├── base.py            # Abstract BaseScraper interface
│   ├── selectors.py       # Configured HTML/CSS selectors for Indeed and ICTJob
│   └── playwright_scraper.py # Playwright anti-bot crawler implementation
├── pipeline/
│   ├── __init__.py
│   ├── models.py          # JobListing Pydantic schema
│   └── normalizer.py      # Deduplication logic using processed_jobs.json
├── sheets/
│   ├── __init__.py
│   └── integration.py     # gspread Service Account sheet sync module
└── drafting/
    ├── __init__.py
    └── engine.py          # Privacy-preserving PII redaction and Cover Letter writer
```

---

## Setup Instructions

### 1. Prerequisites
Ensure you have **Python 3.10+** installed on your system.

### 2. Installation
Clone or navigate to the project directory, set up a virtual environment, and install dependencies:

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install required libraries
pip install -r requirements.txt

# Install Playwright browser binaries
playwright install chromium
```

### 3. Google Sheets Integration Setup
To sync jobs with your Google Sheets:
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project and enable the **Google Sheets API** and **Google Drive API**.
3. Create a **Service Account** under *IAM & Admin -> Service Accounts*.
4. Create and download a new JSON key for the service account.
5. Place the downloaded key in the root of this project and rename it to **`service_account.json`**.
6. Open the JSON file and copy the `"client_email"` value.
7. Create a Google Sheet in your personal Google Drive named **`Belgium Job Search Tracking`**.
8. Click **Share** on your sheet and invite the service account's client email as an **Editor**.

### 4. Environment Variables Setup
Create a file named `.env` in the root of the project:

```ini
# Gemini API Key (Required for cover letter drafting)
GEMINI_API_KEY=your_gemini_api_key_here

# Sheets Settings (Optional overrides)
GOOGLE_SHEET_NAME=Belgium Job Search Tracking
GOOGLE_SHEET_TAB=Jobs
GOOGLE_SERVICE_ACCOUNT_FILE=service_account.json
PROCESSED_JOBS_FILE=processed_jobs.json
SCRAPE_HEADLESS=True
```

### 5. Resume Setup
Create a file named `resume.txt` in the root of the project and paste your resume content there. The engine will redact all contact information (emails, phone numbers, location addresses) before drafting the cover letter.

### 6. Customizing Search Queries
The job hunter crawls multiple portals using search queries derived from [search_config.json](file:///Users/viraltaco_/Library/Mobile%20Documents/com~apple~CloudDocs/Projects/python/Job%20Hunter/search_config.json).

#### Modifying Keywords and Locations
To change what jobs and locations are queried, edit [search_config.json](file:///Users/viraltaco_/Library/Mobile%20Documents/com~apple~CloudDocs/Projects/python/Job%20Hunter/search_config.json) in the root of the project:

```json
{
  "keywords": [
    "C++",
    "Developer"
  ],
  "locations": [
    "Charleroi",
    "Brussels"
  ],
  "sheet_name": "Job Hunter — Belgium ICT Job Search",
  "sheet_tab": "Jobs"
}
```

- **`keywords`**: A list of job title keywords or technical stack terms to search.
- **`locations`**: A list of cities or regions in Belgium to target.
- **`sheet_name`**: Configures the target Google Sheet title.
- **`sheet_tab`**: Configures the tab name in the spreadsheet where listings will be written.

The automation pipeline will execute parallel worker threads for every combination of keyword and location (e.g. `C++` in `Charleroi`, `Developer` in `Charleroi`, etc.).

#### Advanced: Modifying URL Templates and Selectors
If you want to customize how search URLs are structured or add selectors for different websites, you can modify `SELECTOR_CONFIG` in [scraper/selectors.py](file:///Users/viraltaco_/Library/Mobile%20Documents/com~apple~CloudDocs/Projects/python/Job%20Hunter/scraper/selectors.py).

Each portal config specifies a `search_url` template. The scraper replaces `{keyword}` and `{location}` placeholders at runtime with URL-encoded values from your config. For example:
```python
    "ictjob": {
        "search_url": "https://www.ictjob.be/en/search-it-jobs?keywords={keyword}&location={location}",
        "listing_container": "li.search-item",
        "title": "a.job-title",
        ...
    }
```

---

## Usage

Run the tool using the orchestration command:

```bash
# Run a safe local dry-run (won't upload to Google Sheets or hit Gemini API limits)
python3 main.py --dry-run

# Run the complete live automation pipeline
python3 main.py

# Run scraping and sheets logging only (skips Gemini Cover Letter drafting)
python3 main.py --search-only

# Adjust processing limits (e.g. process up to 5 new listings in this run)
python3 main.py --limit 5
```
