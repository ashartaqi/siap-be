import os
import logging
from dotenv import load_dotenv

import litellm
litellm.suppress_debug_info = True

load_dotenv()
logger = logging.getLogger(__name__)

from trulens.core import TruSession, Metric
from trulens.providers.litellm import LiteLLM

# Reuse the same Groq key pattern as the RAGAS harness. If you're keeping a
# second dedicated Groq key for TruLens (recommended, given how often the
# RAGAS harness alone has hit Groq's rate/token caps), set GROQ_API_KEY_TRULENS
# in .env and it'll be preferred; otherwise falls back to the shared key.
GROQ_API_KEY = os.environ.get("GROQ_API_KEY_TRULENS", os.environ["GROQ_API_KEY"])
os.environ["GROQ_API_KEY"] = GROQ_API_KEY  # litellm reads this env var directly

session = TruSession()

provider = LiteLLM(model_engine="groq/llama-3.3-70b-versatile")

# --- RAG Triad metrics, each bound to a specific span/attribute ---
# NOTE: `Feedback` is deprecated in this trulens-core version (2.8.1) in
# favor of `Metric`. All three confirmed working via direct construction
# and inspection -- see PHASE2_5_FINDINGS.md for the full API-discovery
# process (multiple guesses were wrong before landing here).

# Context relevance: record input (question) + retrieval span's context.
# Flagged per the integration plan as the metric most likely to expose
# weaknesses on compound superlative queries and entity disambiguation.
f_context_relevance = (
    Metric(implementation=provider.context_relevance_with_cot_reasons)
    .on_input()
    .on_context(collect_list=False)
)

# Groundedness: retrieval span's full context set vs. record output (the
# final answer). collect_list=True since groundedness needs the whole
# context at once, not scored chunk-by-chunk.
f_groundedness = (
    Metric(implementation=provider.groundedness_measure_with_cot_reasons)
    .on_context(collect_list=True)
    .on_output()
)

# Answer relevance: record input (question) vs. record output (answer).
f_answer_relevance = (
    Metric(implementation=provider.relevance_with_cot_reasons)
    .on_input_output()
)

FEEDBACKS = [f_context_relevance, f_groundedness, f_answer_relevance]