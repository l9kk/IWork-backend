from typing import Dict, List, Any
import re
from app.core.config import settings


async def scan_review_content(content: str) -> Dict[str, List[str]]:
    """
    Simple implementation of AI content scanner that looks for potentially inappropriate content.

    In a production application, this would call an actual AI service like OpenAI's Moderation API.
    """

    # Simple pattern matching for demonstration purposes
    results = {
        "profanity": [],
        "hate_speech": [],
        "personal_info": [],
        "toxic": []
    }

    # Very basic profanity check with simple word list
    profanity_words = ["damn", "hell", "ass", "crap"]
    for word in profanity_words:
        if re.search(r'\b' + word + r'\b', content.lower()):
            results["profanity"].append(word)

    # Very basic hate speech check
    hate_speech_patterns = ["hate", "stupid people", "idiots"]
    for pattern in hate_speech_patterns:
        if pattern in content.lower():
            results["hate_speech"].append(pattern)

    # Basic check for potential personal info
    # Check for email patterns
    email_matches = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', content)
    if email_matches:
        results["personal_info"].extend(email_matches)

    # Check for phone number patterns
    phone_matches = re.findall(
        r'(\d{3}[-\.\s]??\d{3}[-\.\s]??\d{4}|\(\d{3}\)\s*\d{3}[-\.\s]??\d{4}|\d{3}[-\.\s]??\d{4})', content)
    if phone_matches:
        results["personal_info"].extend(phone_matches)

    # Very basic toxicity check
    toxic_patterns = ["terrible", "awful", "worst", "hate", "fire everyone"]
    for pattern in toxic_patterns:
        if pattern in content.lower():
            results["toxic"].append(pattern)

    # Filter out empty categories
    return {k: v for k, v in results.items() if v}