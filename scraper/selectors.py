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
    },
    "forem": {
        "search_url": "https://www.leforem.be/recherche-offres-emploi/resultats?motsCles={keyword}",
        "listing_container": ".job-card, article.job, li.search-result, .card-job, .offres-emplois-liste-item",
        "title": "h2, h3, a.job-title, .title, a.card-link",
        "company": ".company, .employer, .nom-entreprise, .employer-name",
        "url": "a, a.card-link",
        "description": ".description, .snippet, .job-description, .description-job",
        "use_stealth": True,
        "detail_page_desc": "#job-description, .job-description, .content-job"
    },
    "randstad": {
        "search_url": "https://www.randstad.be/nl/vacatures/?q={keyword}&l={location}",
        "listing_container": ".job-item, .card-job, .vacancy-card, .job-card",
        "title": "h3, a.title, .job-title, a.vacancy-link",
        "company": ".company, .employer-name, .client-name",
        "url": "a.job-link, a.vacancy-link, a",
        "description": ".description, .snippet, .job-summary",
        "use_stealth": True,
        "detail_page_desc": ".job-description, .vacancy-description, #job-description"
    },
    "adecco": {
        "search_url": "https://www.adecco.be/nl-be/vacatures?k={keyword}&l={location}",
        "listing_container": ".job-card, .vacancy-card, .card, .job-item",
        "title": "h3, a.title, .job-title",
        "company": ".company-name, .employer, .client-name",
        "url": "a.job-link, a",
        "description": ".description, .snippet, .job-summary",
        "use_stealth": True,
        "detail_page_desc": ".job-description, .vacancy-details"
    },
    "manpower": {
        "search_url": "https://www.manpower.be/en/jobs?search={keyword}&location={location}",
        "listing_container": ".job-item, .job-card, .vacancy-card",
        "title": ".job-title, h3, a.title",
        "company": ".company, .client, .employer",
        "url": "a",
        "description": ".description, .job-summary, .snippet",
        "use_stealth": True,
        "detail_page_desc": ".job-details, .job-description"
    }
}
