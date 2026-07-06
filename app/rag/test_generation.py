# app/rag/test_generation.py
from app.rag.generation import generate_answer

if __name__ == "__main__":
    answer = generate_answer(
        "Who is a good winger with high dribbling?",
        ["Lionel Messi, RW, overall 91, pace 81, dribbling 94, passing 90."]
    )
    print(answer)