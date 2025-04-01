from typing import Dict, List, Union
import re
import json
import httpx
from app.core.config import settings


async def scan_review_content(content: str) -> Dict[str, Union[List[str], bool]]:
    """
    Falls back to basic pattern matching if the API key is not configured or API call fails.
    """
    if settings.GEMINI_API_KEY and content.strip():
        try:
            scan_results = await _scan_with_gemini(content)
        except Exception as e:
            print(f"Gemini API error: {str(e)}")
            scan_results = _scan_with_patterns(content)
    else:
        scan_results = _scan_with_patterns(content)

    is_safe = len(scan_results) == 0

    result = scan_results.copy()
    result["is_safe"] = is_safe

    return result


async def _scan_with_gemini(content: str) -> Dict[str, List[str]]:
    """
    Use Google's Gemini 2.0 Flash API to analyze content for potentially inappropriate material.
    """
    api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

    prompt = f"""
    Analyze the following review content for potentially inappropriate material.
    Identify any instances of:
    1. Profanity
    2. Hate speech
    3. Personal information (emails, phone numbers)
    4. Toxic content (extremely negative, threatening, or harmful language)
    
    Return your analysis as a JSON object with these exact keys:
    "profanity": [list of profane words/phrases found]
    "hate_speech": [list of hate speech instances found]
    "personal_info": [list of personal information found]
    "toxic": [list of toxic content found]
    
    Only include categories with actual findings. If nothing is found in a category, return an empty list.
    Be thorough in your analysis, as this is used for content moderation.
    
    Content to analyze:
    {content}
    """

    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    headers = {"Content-Type": "application/json"}

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{api_url}?key={settings.GEMINI_API_KEY}", json=payload, headers=headers
        )

        if response.status_code != 200:
            raise Exception(
                f"API request failed with status {response.status_code}: {response.text}"
            )

        result = response.json()

        if not result.get("candidates", []):
            raise Exception("No response candidates returned from Gemini API")

        text_result = result["candidates"][0]["content"]["parts"][0]["text"]

        try:
            json_match = re.search(r"({[\s\S]*})", text_result)
            if json_match:
                json_str = json_match.group(1)
                findings = json.loads(json_str)

                expected_keys = ["profanity", "hate_speech", "personal_info", "toxic"]
                for key in expected_keys:
                    if key not in findings:
                        findings[key] = []

                return {k: v for k, v in findings.items() if v}
            else:
                raise Exception("No JSON object found in Gemini response")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON from Gemini response: {e}")
        except Exception as e:
            raise Exception(f"Error processing Gemini response: {e}")


def _scan_with_patterns(content: str) -> Dict[str, List[str]]:
    """
    Used when Gemini API call fails or is not configured.
    """
    results = {"profanity": [], "hate_speech": [], "personal_info": [], "toxic": []}

    profanity_words = ["damn", "hell", "ass", "crap"]
    for word in profanity_words:
        if re.search(r"\b" + word + r"\b", content.lower()):
            results["profanity"].append(word)

    hate_speech_patterns = ["hate", "stupid people", "idiots"]
    for pattern in hate_speech_patterns:
        if pattern in content.lower():
            results["hate_speech"].append(pattern)

    email_matches = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", content)
    if email_matches:
        results["personal_info"].extend(email_matches)

    phone_matches = re.findall(
        r"(\d{3}[-\.\s]??\d{3}[-\.\s]??\d{4}|\(\d{3}\)\s*\d{3}[-\.\s]??\d{4}|\d{3}[-\.\s]??\d{4})",
        content,
    )
    if phone_matches:
        results["personal_info"].extend(phone_matches)

    toxic_patterns = ["terrible", "awful", "worst", "hate", "fire everyone"]
    for pattern in toxic_patterns:
        if pattern in content.lower():
            results["toxic"].append(pattern)

    return {k: v for k, v in results.items() if v}
