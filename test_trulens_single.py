"""
Isolated single-question TruLens test, corrected to wait for async
feedback computation before printing/exiting.

Root cause of earlier NaN values: TruLens computes feedback scores in a
background evaluator thread. Printing results immediately after the
`with tru_app as recording:` block races that background computation --
some scores genuinely hadn't been computed yet at print time, and the
interpreter then exited before they finished, producing the
"cannot schedule new futures after interpreter shutdown" errors.

Fix: call session.wait_for_feedback_results() with the actual record IDs
and feedback names before pulling/printing the results DataFrame.

Run with: python test_trulens_single.py
"""
from app.core.db import SessionLocal
from app.rag.instrumented_service import instrumented_ask_siap
from app.rag.tracing import session, FEEDBACKS
from trulens.apps.app import TruApp


def main():
    db = SessionLocal()

    tru_app = TruApp(
        instrumented_ask_siap,
        app_name="ask_siap",
        app_version="hybrid_retrieval_v1",
        feedbacks=FEEDBACKS,
    )

    with tru_app as recording:
        result = instrumented_ask_siap(db, "Which goalkeepers have the best reflexes?")

    print("ANSWER:", result["answer"])

    # Collect every record ID produced during this call (there will be
    # several -- one per instrumented span, not just one for the top-level
    # question -- confirmed from the earlier run showing 8 record rows for
    # a single question).
    record_ids = [r.record_id for r in recording.records]
    feedback_names = [f.name for f in FEEDBACKS]

    print(f"\nWaiting for feedback on {len(record_ids)} records...")
    session.wait_for_feedback_results(
        record_ids=record_ids,
        feedback_names=feedback_names,
        timeout=120,
    )

    records_df, feedback_cols = session.get_records_and_feedback()
    print("\nFEEDBACK COLUMNS:", feedback_cols)
    print("\nFULL RECORD ROWS:")
    for col in feedback_cols:
        if col in records_df.columns:
            print(f"\n--- {col} ---")
            print(records_df[["record_id", col]].to_string())

    db.close()


if __name__ == "__main__":
    main()