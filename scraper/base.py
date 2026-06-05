from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseScraper(ABC):
    """
    Abstract base class for job scrapers. Enforces consistency in how
    crawlers are initialized, run, and how their data is returned.
    """

    def __init__(self, headless: bool = True, timeout_ms: int = 30000) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms

    @abstractmethod
    def scrape_jobs(self, keyword: str, location: str) -> List[Dict[str, Any]]:
        """
        Scrapes job listings for a given keyword and location.

        Args:
            keyword: The technology or role to search for (e.g., '.NET', 'C++').
            location: The location boundary (e.g., 'Belgium').

        Returns:
            A list of dictionaries, where each dict represents a job listing
            matching the fields: Job Title, Company, URL, and Description.
        """
        pass
