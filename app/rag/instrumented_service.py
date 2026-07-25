from sqlalchemy.orm import Session
from trulens.core.otel.instrument import instrument
from trulens.otel.semconv.trace import SpanAttributes

from app.rag.constraint_extractor import extract_constraints
from app.rag.retrieval import retrieve_relevant_players
from app.rag.player_filters import find_player_name_matches
from app.rag.player_aggregations import run_aggregation, format_aggregation_context
from app.rag.generation import generate_answer
from app.models import DocumentEmbedding


@instrument(name="constraint_extraction", span_type=SpanAttributes.SpanType.UNKNOWN)
def _traced_extract_constraints(question: str) -> dict:
    return extract_constraints(question)


@instrument(name="entity_disambiguation", span_type=SpanAttributes.SpanType.UNKNOWN)
def _traced_name_resolution(db: Session, player_names: list[str]) -> tuple[list[str], list[int]]:
    """Returns (ambiguous_or_missing_notes, resolved_ids)."""
    ambiguous_or_missing = []
    resolved_ids = []
    for name in player_names:
        matches = find_player_name_matches(db, name)
        if len(matches) == 0:
            ambiguous_or_missing.append(f'No player named "{name}" was found in the database.')
        elif len(matches) > 1:
            candidates = "; ".join(
                f"{p.long_name} ({p.short_name}, {p.nationality_name}, plays for {p.club_name or 'no club'})"
                for p in matches
            )
            ambiguous_or_missing.append(f'Multiple players match "{name}": {candidates}. Ask the user which one they mean.')
        else:
            resolved_ids.append(matches[0].id)
    return ambiguous_or_missing, resolved_ids


@instrument(
    span_type=SpanAttributes.SpanType.RETRIEVAL,
    attributes={
        SpanAttributes.RETRIEVAL.QUERY_TEXT: "question",
        SpanAttributes.RETRIEVAL.RETRIEVED_CONTEXTS: "return",
    },
)
def _traced_retrieval(db: Session, question: str, constraints: dict) -> list[str]:
    results = retrieve_relevant_players(db, question, constraints, top_k=5)
    return [r.content for r in results]


@instrument(name="aggregation", span_type=SpanAttributes.SpanType.UNKNOWN)
def _traced_aggregation(db: Session, constraints: dict) -> dict | None:
    return run_aggregation(db, constraints)


@instrument(span_type=SpanAttributes.SpanType.GENERATION)
def _traced_generate_answer(question: str, contexts: list[str], unquantified: list[str] | None) -> str:
    return generate_answer(question, contexts, unquantified)


def instrumented_ask_siap(db: Session, question: str) -> dict:
    """
    Mirrors service.py's ask_siap() control flow exactly, but each stage
    is traced as its own span. Does not modify service.py or any of the
    underlying pipeline modules -- this wraps calls to them.

    NOTE: this must be kept in sync by hand with service.py's control flow
    whenever the real pipeline logic changes -- flagged as a known
    maintenance cost of the "wrap, don't modify" approach.
    """
    constraints = _traced_extract_constraints(question)
    extraction_failed = constraints.pop("_extraction_failed", False)
    unquantified = constraints.get("unquantified_qualifiers")

    degraded_note = None
    if extraction_failed:
        degraded_note = (
            "Note: constraint extraction was temporarily unavailable for this question, "
            "so results below are from a broader search and may be less precise than usual."
        )

    player_names = constraints.get("player_names")
    if player_names:
        ambiguous_or_missing, resolved_ids = _traced_name_resolution(db, player_names)

        if ambiguous_or_missing:
            contexts = ambiguous_or_missing
            if degraded_note:
                contexts = [degraded_note] + contexts
            answer = _traced_generate_answer(question, contexts, unquantified)
            return {"answer": answer, "sources": contexts, "degraded": extraction_failed}

        if resolved_ids:
            docs = (
                db.query(DocumentEmbedding)
                .filter(
                    DocumentEmbedding.source_type == "player",
                    DocumentEmbedding.source_id.in_(resolved_ids),
                )
                .all()
            )
            contexts = [d.content for d in docs]
            if degraded_note:
                contexts = [degraded_note] + contexts
            answer = _traced_generate_answer(question, contexts, unquantified)
            return {"answer": answer, "sources": contexts, "degraded": extraction_failed}

    agg_result = _traced_aggregation(db, constraints)
    if agg_result is not None:
        contexts = [format_aggregation_context(agg_result)]
        if degraded_note:
            contexts = [degraded_note] + contexts
        answer = _traced_generate_answer(question, contexts, unquantified)
        return {"answer": answer, "sources": contexts, "degraded": extraction_failed}

    contexts = _traced_retrieval(db, question, constraints)
    if degraded_note:
        contexts = [degraded_note] + contexts

    answer = _traced_generate_answer(question, contexts, unquantified)
    return {"answer": answer, "sources": contexts, "degraded": extraction_failed}