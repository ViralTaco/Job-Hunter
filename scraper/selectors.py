from typing import Dict, Any

# CSS selectors and configuration parameters for targeted job portals
SELECTOR_CONFIG: Dict[str, Dict[str, Any]] = {
    "ictjob": {
        "search_url": "https://www.ictjob.be/en/search-it-jobs?keywords={keyword}&location={location}",
        "listing_container": "li.search-item",
        "title": "a.job-title",
        "company": "span.company",
        "url": "a.job-title",
        "description": "span.job-details",
        "use_stealth": True,
        "detail_page_desc": ".job-description, .job-details, #job-description"
    },
    "indeed": {
        "search_url": "https://be.indeed.com/jobs?q={keyword}&l={location}",
        "listing_container": ".job_seen_beacon",
        "title": "h2.jobTitle a, a.jcs-JobDetails-title",
        "company": "[data-testid='company-name'], .companyName",
        "url": "h2.jobTitle a, a.jcs-JobDetails-title",
        "description": ".job-snippet, #jobDescriptionText",
        "use_stealth": True,
        "detail_page_desc": "#jobDescriptionText"
    }
}
