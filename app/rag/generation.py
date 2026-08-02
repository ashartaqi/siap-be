import os
import time
import logging
from google import genai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

RETRYABLE_ERROR_MARKERS = ("503", "UNAVAILABLE", "overloaded")
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 3

def _is_retryable(error: Exception) -> bool:
    msg = str(error)
    return any(marker in msg for marker in RETRYABLE_ERROR_MARKERS)


def _is_retryable(error: Exception) -> bool:
    msg = str(error)
    return any(marker in msg for marker in RETRYABLE_ERROR_MARKERS)


def generate_answer(
    question: str,
    contexts: list[str],
    unquantified_qualifiers: list[str] | None = None,
    disambiguation_notes: list[str] | None = None,
) -> str:
    context_block = "\n\n".join(contexts)

    caveat_instruction = ""
    if unquantified_qualifiers:
        qualifiers_str = ", ".join(unquantified_qualifiers)
        caveat_instruction += (
            f"\n\nNote: the question also mentioned '{qualifiers_str}', which wasn't used as a "
            f"hard filter (no specific threshold was stated). Use the relevant attributes already "
            f"present in the player data below to comment on this qualitatively in your answer — "
            f"e.g. mention ages if 'young' was mentioned — rather than ignoring it."
        )

    if disambiguation_notes:
        notes_str = " ".join(disambiguation_notes)
        caveat_instruction += (
            f"\n\nIMPORTANT: {notes_str} Answer the question normally using the assumed player(s), "
            f"but explicitly state at the END of your answer which player you assumed for any "
            f"ambiguous name, and invite the user to provide the full name if you assumed wrong."
        )

    prompt = (
        "You are a football analytics assistant. Answer the user's question "
        "using ONLY the player data provided below. If the data doesn't contain "
        "enough information to answer confidently, say so."
        f"{caveat_instruction}\n\n"
        f"Player data:\n{context_block}\n\n"
        f"Question: {question}"
    )


    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = _client.models.generate_content(
                model="gemini-flash-latest",
                contents=prompt,
            )
            return response.text
        except Exception as e:
            last_error = e
            if _is_retryable(e) and attempt < MAX_RETRIES:
                logger.warning(f"Generation attempt {attempt} failed with retryable error, retrying: {e}")
                time.sleep(RETRY_DELAY_SECONDS)
                continue
            logger.warning(f"Generation failed (attempt {attempt}/{MAX_RETRIES}): {e}")
            break

    return "Sorry, I couldn't generate an answer right now — please try again in a moment."