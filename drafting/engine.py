import re
import time
from typing import Optional
from google import genai
from google.genai import errors

import config


class DraftingEngine:
    """
    Redacts sensitive personal information (PII) from resumes using a combination
    of regex and LLM verification, and drafts tailored cover letters.
    """

    def __init__(self, api_key: str = "") -> None:
        # Fallback to config if not provided explicitly
        self.api_key = api_key or config.GEMINI_API_KEY
        self.client = None
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)

    def _call_gemini_with_retry(
        self, 
        prompt: str, 
        system_instruction: Optional[str] = None, 
        max_retries: int = 3, 
        base_delay: float = 2.0
    ) -> str:
        """
        Invokes the Gemini API (gemini-2.5-flash) with retry logic and exponential backoff.
        """
        if not self.client:
            raise RuntimeError(
                "Gemini Client is not initialized. Please ensure GEMINI_API_KEY is configured."
            )

        for attempt in range(max_retries):
            try:
                # Setup configuration for content generation
                config_kwargs = {}
                if system_instruction:
                    # The modern SDK uses system_instruction parameter or configs.
                    # We can use the default standard prompt structure or configurations
                    pass

                # Let's combine system instruction and prompt for robustness if needed,
                # or pass system instruction in the API config.
                # In google-genai, the system instruction is passed inside the types.GenerateContentConfig
                from google.genai import types
                
                gen_config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.3,
                )

                response = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=gen_config
                )
                
                if response.text:
                    return response.text.strip()
                raise ValueError("Received empty response from Gemini API.")

            except errors.APIError as api_err:
                print(f"[!] Gemini API Error on attempt {attempt + 1}: {api_err}")
                if attempt == max_retries - 1:
                    raise api_err
                time.sleep(base_delay * (2 ** attempt))
            except Exception as e:
                print(f"[!] Unexpected error calling Gemini on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    raise e
                time.sleep(base_delay * (2 ** attempt))

        raise RuntimeError("Failed to obtain response from Gemini API after multiple retries.")

    def redact_resume_regex(self, text: str) -> str:
        """
        Phase 1 Redaction: Rapidly searches and replaces obvious contact patterns
        using regular expressions.
        """
        redacted = text

        # 1. Email Addresses
        email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
        redacted = re.sub(email_pattern, "[EMAIL_REDACTED]", redacted)

        # 2. Belgian & International Phone Numbers
        # Matches: +32 470 12 34 56, 0470/12.34.56, +32470123456, 0499123456, etc.
        phone_pattern = r"(\+?\b(32|0)[-.\s]?[1-9]\d{1,2}[-.\s]?\d{2,3}[-.\s]?\d{2,3}[-.\s]?\d{2,4}\b)"
        redacted = re.sub(phone_pattern, "[PHONE_REDACTED]", redacted)

        # 3. Zip Codes + Municipalities in Belgium (e.g. 1000 Brussels, 2000 Antwerpen)
        # Matches 4-digit zip codes followed by city names
        belgian_zip_pattern = r"\b[1-9]\d{3}\s+[A-Za-zÀ-ÿ]+([-'\s][A-Za-zÀ-ÿ]+)*\b"
        redacted = re.sub(belgian_zip_pattern, "[LOCATION_REDACTED]", redacted)

        return redacted

    def verify_and_redact_llm(self, regex_redacted_text: str) -> str:
        """
        Phase 2 Redaction: Uses Gemini LLM to scan the text and catch any remaining
        subtle PII (e.g., full names, specific street addresses, social media profiles).
        """
        system_instruction = (
            "You are a strict PII Redaction Agent. Analyze the provided resume text. "
            "Your sole objective is to find any remaining personally identifiable information (PII) "
            "that the regex filters missed, such as person names, specific home/street addresses, "
            "social media profile handles, or specific dates/IDs, and replace them with "
            "appropriate placeholders (e.g., [NAME_REDACTED], [ADDRESS_REDACTED], [LINK_REDACTED]). "
            "Do NOT remove technical skills, project names, or university/company names unless they directly "
            "identify the user. "
            "Return ONLY the cleaned and redacted resume text. Do not include any greeting, introduction, "
            "or side explanations."
        )

        prompt = f"Resume Snippet to analyze:\n\n{regex_redacted_text}"
        
        try:
            cleaned_text = self._call_gemini_with_retry(
                prompt=prompt, 
                system_instruction=system_instruction
            )
            return cleaned_text
        except Exception as e:
            print(f"[!] LLM Redaction verification failed: {e}. Falling back to Regex-only redaction.")
            return regex_redacted_text

    def redact_resume(self, text: str) -> str:
        """
        Executes the dual-phase redaction process.
        """
        print("[*] Performing regex-based pre-redaction...")
        regex_cleaned = self.redact_resume_regex(text)
        
        if self.client:
            print("[*] Performing LLM-based redaction verification...")
            return self.verify_and_redact_llm(regex_cleaned)
        
        print("[!] Gemini client not available, skipping LLM redaction verification.")
        return regex_cleaned

    def generate_cover_letter(self, clean_resume: str, job_description: str) -> str:
        """
        Uses the clean resume and job description to draft a tailored cover letter.
        """
        system_instruction = (
            "You are a professional career coach and technical copywriter. "
            "Your task is to draft a tailored, professional cover letter for an applicant "
            "seeking a Junior Full-Stack .NET Developer role in Belgium. "
            "You must match the applicant's technical background (which may include .NET, C#, C++, SQL, "
            "and Full-Stack principles) to the requirements in the job description. "
            "Ensure the tone is professional, enthusiastic, and humble (suitable for a junior profile). "
            "You must ensure NO private data is leaked. Use the redacted tags provided in the resume "
            "(e.g., [NAME_REDACTED], [EMAIL_REDACTED]) or standard placeholders (e.g., [Hiring Manager Name], [Date]) "
            "where personal details are expected. "
            "Return ONLY the drafted cover letter in markdown. Do not include markdown code fence wrappers, "
            "conversational intro/outro notes, or meta commentary."
        )

        prompt = (
            f"--- APPLICANT REDACTED RESUME ---\n{clean_resume}\n\n"
            f"--- TARGET JOB DESCRIPTION ---\n{job_description}\n\n"
            f"Please generate the cover letter now."
        )

        print("[*] Generating cover letter using Gemini...")
        return self._call_gemini_with_retry(
            prompt=prompt, 
            system_instruction=system_instruction
        )
class MockDraftingEngine(DraftingEngine):
    """
    Mock engine to run validation tests without hitting the Gemini API.
    """
    def redact_resume(self, text: str) -> str:
        print("[*] (Mock) Simulating resume redaction.")
        return self.redact_resume_regex(text)

    def generate_cover_letter(self, clean_resume: str, job_description: str) -> str:
        print("[*] (Mock) Simulating cover letter drafting.")
        return (
            "Subject: Application for Junior Full-Stack .NET Developer\n\n"
            "Dear Hiring Team,\n\n"
            "I am writing to express my strong interest in the Junior Full-Stack .NET Developer position in Belgium. "
            "Based on your job description, I believe my background aligns well with your team's needs.\n\n"
            "Best regards,\n[NAME_REDACTED]"
        )
