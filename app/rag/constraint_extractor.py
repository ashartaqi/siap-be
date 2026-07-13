import os
import json
import logging
from google import genai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

EXTRACTION_PROMPT = """You are a constraint extraction engine for a football player database.
Extract ONLY the structured filters explicitly stated in the question below.
Do not guess or infer anything not stated. Omit keys entirely if not mentioned (never use null).

Valid position values are EXACTLY these strings — use ONLY these, never invent variants:
CB, LB, RB, CDM, CM, CAM, LM, RM, LW, RW, CF, ST, GK

Return ONLY valid JSON, no markdown fences, no explanation, matching this shape:

{{
  "positions": ["ST", "CB", ...],
  "age_min": integer,
  "age_max": integer,
  "preferred_foot": "Left" or "Right",
  "nationality": string,
  "overall_min": integer,
  "overall_max": integer,
  "stats": {{"pace_min": integer, "shooting_min": integer, "passing_min": integer,
             "dribbling_min": integer, "defending_min": integer, "physic_min": integer}},
  "goalkeeper_stats": {{"diving_min": integer, "handling_min": integer, "kicking_min": integer,
                        "positioning_min": integer, "reflexes_min": integer, "speed_min": integer}}
}}

Question: {question}
"""


def extract_constraints(question: str) -> dict:
    prompt = EXTRACTION_PROMPT.format(question=question)
    try:
        response = _client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"Constraint extraction failed, falling back to vector search: {e}")
        return {}