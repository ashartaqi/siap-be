import os
import json
import logging
from google import genai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

VALID_SORT_FIELDS = {
    "overall", "pace", "shooting", "passing", "dribbling", "defending", "physic",
    "diving", "handling", "kicking", "positioning", "reflexes", "speed",
}

EXTRACTION_PROMPT = """You are a constraint extraction engine for a football player database.
Extract ONLY the structured filters explicitly stated in the question below.
Do not guess or infer thresholds that aren't stated. Omit keys entirely if not mentioned (never use null).

Valid position values are EXACTLY these strings — use ONLY these, never invent variants:
CB, LB, RB, CDM, CM, CAM, LM, RM, LW, RW, CF, ST, GK

SORT INTENT: if the question asks for the "best", "top", "fastest", "highest", "most" (etc.)
players by some quality — rather than stating a hard numeric threshold — set "sort_by" to the
single most relevant stat field, and "sort_direction" to "desc" (or "asc" for "worst"/"lowest").
Valid sort_by values are EXACTLY: overall, pace, shooting, passing, dribbling, defending, physic,
diving, handling, kicking, positioning, reflexes, speed.

If the question names a specific stat explicitly (e.g. "best passing", "highest overall rating"),
use that stat. If it does NOT name a stat but implies one through role or position
(e.g. "best defenders" -> defending, "fastest players" -> pace, "best goalkeepers" -> positioning
or reflexes as most representative, "best finishers"/"best strikers" for scoring -> shooting),
prefer that role-appropriate stat over "overall". Only use "overall" when the question is
genuinely about general quality with no implied specialism (e.g. "best players overall",
"highest rated players").


AGGREGATION INTENT: if the question asks for a computed summary across MANY players
rather than a list of individual players — e.g. "how many...", "what's the average...",
"which league/nationality/club has the highest/most...", "compare X across leagues" —
set "aggregation" to an object with:
  "type": one of "count", "avg", "max", "min", "sum"
  "field": the stat/column being aggregated (e.g. "defending", "overall", "pace") —
           omit "field" entirely if type is "count" and no specific stat is involved
  "group_by": one of "league_name", "nationality_name", "club_name", "position",
              "preferred_foot" — omit if the question wants a single overall number,
              not broken down by group
Only set "aggregation" when the question clearly wants a computed number/summary,
NOT a list of specific players. If it wants specific players (even ranked), use
sort_by instead, not aggregation. Do not set both in the same response.

Do not set both a "_min" threshold AND sort_by for the same stat — if there's no explicit number,
use sort_by, not a guessed threshold.

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
                        "positioning_min": integer, "reflexes_min": integer, "speed_min": integer}},
  "sort_by": "reflexes",
  "sort_direction": "desc"
}}

Question: {question}
"""


def extract_constraints(question: str) -> dict:
    prompt = EXTRACTION_PROMPT.format(question=question)
    try:
        response = _client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
        )
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
        result = json.loads(raw)

        # Defensive: drop sort_by if it's not a recognized stat field
        if result.get("sort_by") and result["sort_by"] not in VALID_SORT_FIELDS:
            logger.warning(f"Extractor returned invalid sort_by: {result['sort_by']!r}, dropping")
            result.pop("sort_by", None)
            result.pop("sort_direction", None)

        return result
    except Exception as e:
        logger.warning(f"Constraint extraction failed, falling back to vector search: {e}")
        return {}