from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class JobListing(BaseModel):
    """
    Standardized schema representing a job listing. Performs validation
    and structural integrity checks on the raw scraped details.
    """
    job_title: str = Field(..., description="The title of the job listing.")
    company: str = Field(..., description="The hiring company name.")
    url: str = Field(..., description="The direct web URL to the job listing.")
    description: str = Field(..., description="The main text description of the job.")
    location: str = Field("Belgium", description="The geographical location of the job.")
    scraped_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z",
        description="ISO UTC timestamp of when the listing was scraped."
    )
    source_site: str = Field(..., description="The source portal where the listing was scraped.")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validates that the string is a valid HTTP or HTTPS URL."""
        if not v.startswith("http://") and not v.startswith("https://"):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("job_title", "company")
    @classmethod
    def clean_text_fields(cls, v: str) -> str:
        """Removes duplicate whitespace and cleans text values."""
        return " ".join(v.split())
