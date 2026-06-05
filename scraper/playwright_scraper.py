import time
import random
import urllib.parse
from typing import List, Dict, Any
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

from scraper.base import BaseScraper
from scraper.selectors import SELECTOR_CONFIG


class PlaywrightScraper(BaseScraper):
    """
    Playwright-based synchronous job scraper with built-in anti-bot evasion
    and fallback mechanisms for extracting job listings.
    """

    def __init__(self, headless: bool = True, timeout_ms: int = 30000) -> None:
        super().__init__(headless=headless, timeout_ms=timeout_ms)
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
        ]

    def _get_random_user_agent(self) -> str:
        return random.choice(self.user_agents)

    def _apply_anti_bot_measures(self, context: BrowserContext) -> None:
        """Injects stealth settings and custom headers into the context."""
        context.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9,fr-BE;q=0.8,nl-BE;q=0.7",
            "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Upgrade-Insecure-Requests": "1"
        })

    def _human_scroll(self, page: Page) -> None:
        """Simulates human scrolling behavior to trigger lazy-loaded elements and trigger page states."""
        try:
            for _ in range(random.randint(2, 4)):
                scroll_height = random.randint(300, 700)
                page.evaluate(f"window.scrollBy(0, {scroll_height})")
                time.sleep(random.uniform(0.5, 1.5))
        except Exception as e:
            print(f"[!] Error while simulating scrolling: {e}")

    def scrape_jobs(self, keyword: str, location: str) -> List[Dict[str, Any]]:
        """
        Main method to iterate over target portals and extract job details.
        """
        results: List[Dict[str, Any]] = []

        print(f"[*] Starting Playwright Scraper for keyword '{keyword}' in '{location}'...")

        with sync_playwright() as p:
            browser: Browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-infobars"
                ]
            )
            
            # Select random user agent and set screen size
            user_agent = self._get_random_user_agent()
            context: BrowserContext = browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1920, "height": 1080}
            )
            self._apply_anti_bot_measures(context)
            
            for site_name, config in SELECTOR_CONFIG.items():
                print(f"[*] Scraping site: {site_name}")
                try:
                    page: Page = context.new_page()
                    page.set_default_timeout(self.timeout_ms)
                    
                    # Generate search URL
                    encoded_keyword = urllib.parse.quote(keyword)
                    encoded_location = urllib.parse.quote(location)
                    url = config["search_url"].format(keyword=encoded_keyword, location=encoded_location)
                    
                    print(f"[*] Navigating to: {url}")
                    response = page.goto(url, wait_until="domcontentloaded")
                    
                    if not response or response.status >= 400:
                        print(f"[!] Warning: Page returned status {response.status if response else 'None'}")
                    
                    time.sleep(random.uniform(2.0, 4.0)) # Let page settle
                    self._human_scroll(page)

                    # Extract job listing elements
                    listings = page.query_selector_all(config["listing_container"])
                    print(f"[*] Found {len(listings)} elements matching selector '{config['listing_container']}' on {site_name}")
                    
                    for index, item in enumerate(listings[:10]):  # Limit to top 10 per keyword/site to avoid rate limits
                        try:
                            # 1. Title
                            title_elem = item.query_selector(config["title"])
                            job_title = title_elem.inner_text().strip() if title_elem else "N/A"
                            
                            # 2. Company
                            company_elem = item.query_selector(config["company"])
                            company = company_elem.inner_text().strip() if company_elem else "N/A"
                            
                            # 3. URL
                            job_url = "N/A"
                            if title_elem:
                                href = title_elem.get_attribute("href")
                                if href:
                                    # Handle relative paths
                                    if href.startswith("/"):
                                        parsed_base = urllib.parse.urlparse(url)
                                        job_url = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
                                    else:
                                        job_url = href
                            
                            # 4. Description snippet
                            desc_elem = item.query_selector(config["description"])
                            description = desc_elem.inner_text().strip() if desc_elem else "N/A"
                            
                            if job_title == "N/A" and company == "N/A" and job_url == "N/A":
                                # Skip completely empty rows
                                continue

                            # Navigate to detail page if possible to get complete description
                            full_description = description
                            if job_url != "N/A" and config.get("detail_page_desc"):
                                full_description = self._scrape_job_details(context, job_url, config["detail_page_desc"], description)

                            results.append({
                                "job_title": job_title,
                                "company": company,
                                "url": job_url,
                                "description": full_description,
                                "location": location,
                                "source_site": site_name
                            })
                            
                        except Exception as item_err:
                            print(f"[!] Error parsing listing {index} on {site_name}: {item_err}")
                            continue
                            
                    page.close()
                    
                except Exception as site_err:
                    print(f"[!] Error scraping {site_name}: {site_err}")
                    continue

            context.close()
            browser.close()

        print(f"[*] Scraping completed. Gathered {len(results)} listings.")
        return results

    def _scrape_job_details(self, context: BrowserContext, url: str, selector: str, fallback_desc: str) -> str:
        """
        Navigates to the detail page of a job listing to extract the full description.
        If navigation fails, defaults back to the list-page snippet.
        """
        try:
            detail_page = context.new_page()
            detail_page.set_default_timeout(15000)  # Lower timeout for detail pages
            
            # Navigate with a small delay to simulate reading listings
            time.sleep(random.uniform(1.0, 2.5))
            detail_page.goto(url, wait_until="domcontentloaded")
            
            # Wait for selector to load
            detail_page.wait_for_selector(selector, timeout=5000)
            
            desc_elem = detail_page.query_selector(selector)
            if desc_elem:
                text = desc_elem.inner_text().strip()
                detail_page.close()
                return text if len(text) > len(fallback_desc) else fallback_desc
                
            detail_page.close()
        except Exception:
            # Silently catch details navigation failures and use list page snippet
            pass
        return fallback_desc
