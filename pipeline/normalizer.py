import json
from pathlib import Path
from typing import List, Dict, Any, Set
from pipeline.models import JobListing


class DataPipeline:
    """
    Handles data validation, normalization, and URL-based deduplication
    to prevent processing of redundant listings.
    """

    def __init__(self, cache_file_path: Path) -> None:
        self.cache_file_path = cache_file_path
        self.processed_urls: Set[str] = self._load_cache()

    def _load_cache(self) -> Set[str]:
        """Loads cached URLs from the JSON file."""
        if not self.cache_file_path.exists():
            return set()
        try:
            with open(self.cache_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(data)
        except Exception as e:
            print(f"[!] Error loading URL cache file: {e}")
        return set()

    def _save_cache(self) -> None:
        """Saves current processed URLs to the JSON file."""
        try:
            with open(self.cache_file_path, "w", encoding="utf-8") as f:
                json.dump(list(self.processed_urls), f, indent=4)
        except Exception as e:
            print(f"[!] Error saving URL cache file: {e}")

    def normalize_and_validate(self, raw_listings: List[Dict[str, Any]]) -> List[JobListing]:
        """
        Converts list of raw scraper dictionary structures into validated JobListing objects.
        Filters out listings that fail Pydantic schema validation.
        """
        valid_listings: List[JobListing] = []
        for raw in raw_listings:
            try:
                # Ensure the core fields are filled out
                listing = JobListing(
                    job_title=raw.get("job_title", "N/A"),
                    company=raw.get("company", "N/A"),
                    url=raw.get("url", "N/A"),
                    description=raw.get("description", "N/A"),
                    location=raw.get("location", "Belgium"),
                    source_site=raw.get("source_site", "Unknown")
                )
                valid_listings.append(listing)
            except Exception as val_err:
                print(f"[!] Schema validation rejected listing: {raw.get('url')} | Error: {val_err}")
                continue
        return valid_listings

    def deduplicate(self, listings: List[JobListing]) -> List[JobListing]:
        """
        Filters out job listings that have already been processed in previous runs.
        Also updates the local tracking file with new URLs.
        """
        new_listings: List[JobListing] = []
        for listing in listings:
            if listing.url not in self.processed_urls:
                new_listings.append(listing)
                self.processed_urls.add(listing.url)

        if new_listings:
            self._save_cache()
            print(f"[*] Pipeline filtered out {len(listings) - len(new_listings)} duplicates. {len(new_listings)} new listings remaining.")
        else:
            print("[*] Pipeline processed 0 new listings (all inputs were duplicates).")

        return new_listings
