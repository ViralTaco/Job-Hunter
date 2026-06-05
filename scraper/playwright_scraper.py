import time
import re
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
        self.scraped_urls_in_session = set()

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
                # Generate search URL
                encoded_keyword = urllib.parse.quote(keyword)
                encoded_location = urllib.parse.quote(location)
                
                has_location = "{location}" in config["search_url"]
                if has_location:
                    url = config["search_url"].format(keyword=encoded_keyword, location=encoded_location)
                else:
                    url = config["search_url"].format(keyword=encoded_keyword)
                
                # Check for redundant scrapes in this session
                if url in self.scraped_urls_in_session:
                    print(f"[*] Skipping {site_name} for location '{location}' (already scraped for keyword '{keyword}')")
                    continue
                self.scraped_urls_in_session.add(url)

                print(f"[*] Scraping site: {site_name}")
                try:
                    page: Page = context.new_page()
                    page.set_default_timeout(self.timeout_ms)
                    
                    print(f"[*] Navigating to: {url}")
                    response = page.goto(url, wait_until="domcontentloaded")
                    
                    if not response or response.status >= 400:
                        print(f"[!] Warning: Page returned status {response.status if response else 'None'}")
                    
                    # 1. Bypass Cookie Consent Banners
                    if "google.com" in url:
                        try:
                            accept_btn = page.locator("button#L2AGLb")
                            if accept_btn.count() > 0:
                                print("[*] Google consent banner detected. Clicking 'Accept all'...")
                                accept_btn.first.click()
                                page.wait_for_load_state("domcontentloaded")
                                time.sleep(1.0)
                        except Exception as e:
                            print(f"[!] Error bypassing Google consent: {e}")
                            
                    elif "leforem.be" in url:
                        try:
                            accept_btn = page.locator("button:has-text('autorise tous')")
                            if accept_btn.count() > 0:
                                print("[*] Forem cookie banner detected. Clicking...")
                                accept_btn.first.click()
                                time.sleep(1.0)
                        except Exception as e:
                            print(f"[!] Error bypassing Forem cookie banner: {e}")
                            
                    elif "adecco.be" in url:
                        try:
                            page.evaluate("""() => {
                                const sdk = document.getElementById('onetrust-consent-sdk');
                                if (sdk) sdk.remove();
                                const filter = document.querySelector('.onetrust-pc-dark-filter');
                                if (filter) filter.remove();
                                document.body.style.overflow = 'visible';
                            }""")
                            time.sleep(1.0)
                        except Exception as e:
                            print(f"[!] Error bypassing Adecco cookie banner: {e}")
                    
                    time.sleep(random.uniform(2.0, 4.0)) # Let page settle
                    self._human_scroll(page)

                    # 2. Wait for listing container to load (helps dynamic/SPA sites)
                    try:
                        page.wait_for_selector(config["listing_container"], timeout=8000)
                    except Exception:
                        pass

                    # Extract job listing elements
                    listings = page.query_selector_all(config["listing_container"])
                    print(f"[*] Found {len(listings)} elements matching selector '{config['listing_container']}' on {site_name}")
                    
                    for index, item in enumerate(listings[:10]):  # Limit to top 10 per keyword/site to avoid rate limits
                        try:
                            # 1. Title
                            title_elem = item.query_selector(config["title"])
                            job_title = title_elem.inner_text().strip() if title_elem else "N/A"
                            
                            # Clean Forem company label prefix if title contains it
                            if site_name == "forem" and "Nom d'entreprise" in job_title:
                                job_title = job_title.split("Nom d'entreprise :")[0].strip()
                            
                            # 2. Company
                            company_elem = item.query_selector(config["company"])
                            company = company_elem.inner_text().strip() if company_elem else "N/A"
                            
                            # Clean Forem company label prefix
                            if site_name == "forem" and "Nom d'entreprise" in company:
                                company = company.replace("Nom d'entreprise :", "").strip()
                            
                            # 3. URL
                            job_url = "N/A"
                            url_elem = item.query_selector(config["url"])
                            href = url_elem.get_attribute("href") if url_elem else None
                            
                            # Fallback 1: check if the card container itself has a href attribute
                            if (not href or href in ["#", "javascript:void(0)"]):
                                container_href = item.get_attribute("href")
                                if container_href and container_href not in ["#", "javascript:void(0)"]:
                                    href = container_href
                                    
                            # Fallback 2: search for ANY anchor tag with a valid href inside the container
                            if (not href or href in ["#", "javascript:void(0)"]):
                                try:
                                    all_links = item.query_selector_all("a")
                                    for link in all_links:
                                        link_href = link.get_attribute("href")
                                        if link_href and link_href not in ["#", "javascript:void(0)"]:
                                            href = link_href
                                            break
                                except Exception:
                                    pass
                                
                            if href:
                                # Handle relative paths
                                if href.startswith("/"):
                                    parsed_base = urllib.parse.urlparse(url)
                                    job_url = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
                                else:
                                    # Remove Google redirection wrappers if present
                                    if "url?q=" in href:
                                        match = re.search(r"url\?q=([^&]+)", href)
                                        if match:
                                            href = urllib.parse.unquote(match.group(1))
                                    job_url = href
                                    
                            # Handle Adecco split-pane details extraction
                            if site_name == "adecco":
                                try:
                                    item.click(force=True)
                                    time.sleep(1.5)
                                    job_url = page.url
                                except Exception as click_err:
                                    print(f"[!] Error clicking Adecco card: {click_err}")
                            
                            # 4. Description snippet
                            desc_elem = item.query_selector(config["description"])
                            description = desc_elem.inner_text().strip() if desc_elem else "N/A"
                            
                            if job_title == "N/A" and company == "N/A" and job_url == "N/A":
                                # Skip completely empty rows
                                continue

                            # Navigate to detail page if possible to get complete description
                            full_description = description
                            if job_url != "N/A" and config.get("detail_page_desc"):
                                if site_name == "adecco":
                                    # Extract from the same page details pane
                                    detail_elem = page.query_selector(config["detail_page_desc"])
                                    full_description = detail_elem.inner_text().strip() if detail_elem else description
                                else:
                                    full_description = self._scrape_job_details(context, job_url, config["detail_page_desc"], description)

                            # Identify original source domain from URL
                            source_site = site_name
                            if site_name == "google" and job_url != "N/A":
                                for domain in ["ictjob", "indeed", "forem", "randstad", "adecco", "manpower"]:
                                    if domain in job_url:
                                        source_site = domain
                                        break

                            results.append({
                                "job_title": job_title,
                                "company": company,
                                "url": job_url,
                                "description": full_description,
                                "location": location,
                                "source_site": source_site
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
