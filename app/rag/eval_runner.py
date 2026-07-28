import os
import time
from dotenv import load_dotenv
load_dotenv()

from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from datasets import Dataset
from ragas.run_config import RunConfig

from ragas import evaluate
from ragas.metrics import (
    context_precision,
    context_recall,
    faithfulness,
    answer_relevancy,
)

from app.core.db import SessionLocal
from app.rag.service import ask_siap
from app.rag.eval_dataset import EVAL_QUESTIONS


def build_eval_samples():
    db = SessionLocal()
    questions, contexts, answers, ground_truths = [], [], [], []
    try:
        for item in EVAL_QUESTIONS:
            result = ask_siap(db, item["question"])
            questions.append(item["question"])
            contexts.append(result["sources"])
            answers.append(result["answer"])
            ground_truths.append(item["ground_truth"])
            time.sleep(15)
    finally:
        db.close()

    return Dataset.from_dict({
        "question": questions,
        "contexts": contexts,
        "answer": answers,
        "ground_truth": ground_truths,
    })


def run_eval():
    dataset = build_eval_samples()

    judge_llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0,
    )
    judge_embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    results = evaluate(
        dataset=dataset,
        metrics=[context_precision, context_recall, faithfulness, answer_relevancy],
        llm=judge_llm,
        embeddings=judge_embeddings,
        run_config=RunConfig(timeout=120, max_workers=2),
    )

    return results


if __name__ == "__main__":
    results = run_eval()
    print(results)
    df = results.to_pandas()
    print(df.to_string())