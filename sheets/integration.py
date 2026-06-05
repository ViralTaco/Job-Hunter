import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import gspread
from google.oauth2.service_account import Credentials

from pipeline.models import JobListing


class GoogleSheetsConnector:
    """
    Connects to Google Sheets via gspread using a Service Account file.
    Ensures sheet initialization and appends normalized job records.
    """

    def __init__(self, credentials_path: Path, sheet_name: str, tab_name: str = "Jobs") -> None:
        self.credentials_path = credentials_path
        self.sheet_name = sheet_name
        self.tab_name = tab_name
        self.client: Optional[gspread.Client] = None
        self.sheet: Optional[gspread.Worksheet] = None
        self.headers = [
            "Job Title", 
            "Company", 
            "URL", 
            "Location", 
            "Scraped Date", 
            "Source Site", 
            "Status", 
            "Cover Letter Draft"
        ]

    def _get_client_email(self) -> str:
        """Extracts the service account client email for instructions."""
        try:
            with open(self.credentials_path, "r", encoding="utf-8") as f:
                creds_data = json.load(f)
                return creds_data.get("client_email", "your-service-account-email@...")
        except Exception:
            return "your-service-account-email@..."

    def connect(self) -> None:
        """Authenticates with Google APIs and opens the worksheet."""
        if not self.credentials_path.exists():
            raise FileNotFoundError(
                f"Google Service Account key file not found at '{self.credentials_path}'. "
                "Please place your credentials JSON file there or adjust your .env settings."
            )

        print("[*] Authenticating with Google Sheets API...")
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        try:
            creds = Credentials.from_service_account_file(
                str(self.credentials_path), 
                scopes=scopes
            )
            self.client = gspread.authorize(creds)
        except Exception as auth_err:
            raise RuntimeError(f"Failed to authenticate with Google APIs: {auth_err}")

        # Open the spreadsheet
        try:
            spreadsheet = self.client.open(self.sheet_name)
        except gspread.SpreadsheetNotFound:
            client_email = self._get_client_email()
            raise RuntimeError(
                f"Spreadsheet '{self.sheet_name}' not found. "
                "Please perform the following steps:\n"
                f"1. Create a Google Sheet named '{self.sheet_name}' in your Google Drive.\n"
                f"2. Click the 'Share' button in the upper-right corner of the sheet.\n"
                f"3. Add the service account client email: '{client_email}' as an 'Editor'.\n"
                "4. Rerun this program."
            )
        except Exception as e:
            raise RuntimeError(f"Error accessing Google Spreadsheet: {e}")

        # Access or create the specific tab
        try:
            self.sheet = spreadsheet.worksheet(self.tab_name)
            print(f"[*] Connected to worksheet tab '{self.tab_name}' successfully.")
        except gspread.WorksheetNotFound:
            print(f"[*] Worksheet tab '{self.tab_name}' not found. Creating it...")
            try:
                self.sheet = spreadsheet.add_worksheet(title=self.tab_name, rows=1000, cols=len(self.headers))
                self._initialize_headers()
            except Exception as create_err:
                raise RuntimeError(f"Failed to create new worksheet tab: {create_err}")
        
        # Ensure headers exist
        self._ensure_headers()

    def _initialize_headers(self) -> None:
        """Writes headers to the first row of an empty sheet."""
        if self.sheet:
            self.sheet.insert_row(self.headers, index=1)
            # Format headers (bold and colored light grey)
            self.sheet.format("A1:H1", {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}
            })
            print("[*] Initialized sheet headers.")

    def _ensure_headers(self) -> None:
        """Verifies that the headers match the expected schema, inserting them if empty."""
        if not self.sheet:
            return
        
        first_row = self.sheet.row_values(1)
        if not first_row or len(first_row) == 0:
            self._initialize_headers()
        else:
            # Check if any columns are missing and print warnings
            for h in self.headers:
                if h not in first_row:
                    print(f"[!] Warning: Column header '{h}' is missing in the Google Sheet.")

    def append_job(self, listing: JobListing, status: str = "Scraped", cover_letter: str = "") -> None:
        """Appends a single JobListing record to the tracking sheet."""
        if not self.sheet:
            raise RuntimeError("Cannot append row: Not connected to Google Sheets.")

        row_data = [
            listing.job_title,
            listing.company,
            listing.url,
            listing.location,
            listing.scraped_at,
            listing.source_site,
            status,
            cover_letter
        ]
        
        try:
            self.sheet.append_row(row_data)
            print(f"[*] Successfully logged job: '{listing.job_title}' at '{listing.company}'")
        except Exception as e:
            print(f"[!] Failed to append job to Google Sheet: {e}")

    def append_jobs_batch(self, listings: List[JobListing], default_status: str = "Scraped") -> None:
        """
        Appends multiple job listing rows to the sheet in a single network request.
        """
        if not self.sheet:
            raise RuntimeError("Cannot append rows: Not connected to Google Sheets.")
        
        if not listings:
            return

        rows = []
        for item in listings:
            rows.append([
                item.job_title,
                item.company,
                item.url,
                item.location,
                item.scraped_at,
                item.source_site,
                default_status,
                ""  # Empty cover letter to be filled in later or written in place
            ])

        try:
            self.sheet.append_rows(rows)
            print(f"[*] Logged {len(listings)} new jobs to Google Sheets in batch mode.")
        except Exception as e:
            print(f"[!] Batch append to Google Sheets failed: {e}")
            # Fallback to single append
            print("[*] Retrying with single row appends...")
            for item in listings:
                self.append_job(item, default_status)
class DryRunSheetsConnector(GoogleSheetsConnector):
    """
    Simulates Google Sheets integration for local dry-runs without requiring API access.
    """
    def connect(self) -> None:
        print("[*] (Dry-Run) Simulating successful connection to Google Sheets.")

    def append_job(self, listing: JobListing, status: str = "Scraped", cover_letter: str = "") -> None:
        print(f"[*] (Dry-Run Log) Job Title: {listing.job_title} | Company: {listing.company} | Status: {status}")
        if cover_letter:
            print(f"    -> Cover letter drafted successfully ({len(cover_letter)} chars)")

    def append_jobs_batch(self, listings: List[JobListing], default_status: str = "Scraped") -> None:
        print(f"[*] (Dry-Run Log) Batch logging {len(listings)} listings.")
        for item in listings:
            self.append_job(item, default_status)
