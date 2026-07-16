import os
import logging
from google import genai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def generate_answer(question: str, contexts: list[str]) -> str:
    context_block = "\n\n".join(contexts)

    prompt = (
        "You are a football analytics assistant. Answer the user's question "
        "using ONLY the player data provided below. If the data doesn't contain "
        "enough information to answer confidently, say so.\n\n"
        f"Player data:\n{context_block}\n\n"
        f"Question: {question}"
    )

    try:
        response = _client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
        )
        return response.text
    except Exception as e:
        logger.warning(f"Generation failed: {e}")
        return "Sorry, I couldn't generate an answer right now — please try again in a moment."