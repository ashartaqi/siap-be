import json
import time

from app.core.db import SessionLocal
from app.rag.eval_dataset import EVAL_QUESTIONS
from app.rag.instrumented_service import instrumented_ask_siap
from app.rag.tracing import session, FEEDBACKS
from trulens.apps.app import TruApp


def run_trulens_eval():
    db = SessionLocal()

    tru_app = TruApp(
        instrumented_ask_siap,
        app_name="ask_siap",
        app_version="hybrid_retrieval_v1",
        feedbacks=FEEDBACKS,
    )

    report = []

    for item in EVAL_QUESTIONS:
        question = item["question"]
        with tru_app as recording:
            result = instrumented_ask_siap(db, question)

        record = recording.get()

        report.append({
            "question": question,
            "ground_truth": item.get("ground_truth"),
            "answer": result["answer"],
            "degraded": result.get("degraded", False),
            "record_id": record.record_id,
        })

        time.sleep(15)  # same Groq-quota pacing as the RAGAS harness

    db.close()

    with open("trulens_eval_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    run_trulens_eval()