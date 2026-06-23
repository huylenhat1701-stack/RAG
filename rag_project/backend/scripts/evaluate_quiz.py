"""
=============================================================
TANG 3: Danh gia chat luong Quiz (Generation Quality)
=============================================================
Chay:
    cd rag_project
    python -m backend.scripts.evaluate_quiz

Mo ta:
    - Tu dong sinh 10 cau hoi quiz tu tai lieu da indexed
    - Dung LLM kiem tra:
        * Groundedness: Cau hoi va dap an co xuat phat tu chunk goc khong?
        * Plausibility: Cac lua chon sai co hop ly khong (khong qua de doan)?
    - Tinh ty le % cau dat yeu cau chat luong
    - Luu ket qua ra CSV
"""

import sys
import csv
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.db.database import SessionLocal
from backend.services.llm_service import get_llm_service
from backend.services.rag_service import generate_quiz
from backend.repositories.document_repo import DocumentRepository


QUALITY_THRESHOLD = 3  # Diem >= 3/5 la dat


def judge_quiz_question(llm_service, question_data: dict, chunk_text: str) -> dict:
    """
    Dung LLM danh gia chat luong 1 cau hoi quiz.
    Tra ve {groundedness, plausibility, reasoning}
    """
    q_text  = question_data.get("question", "")
    options = question_data.get("options", {})
    answer  = question_data.get("answer", "A")
    expl    = question_data.get("explanation", "")

    options_str = "\n".join(f"  {k}: {v}" for k, v in options.items())

    judge_prompt = (
        f"Ban la giam khao danh gia cau hoi trac nghiem. Cham diem theo 2 tieu chi (thang 1-5).\n\n"
        f"DOAN TAI LIEU GOC:\n{chunk_text[:500]}\n\n"
        f"CAU HOI: {q_text}\n"
        f"LUA CHON:\n{options_str}\n"
        f"DAP AN DUNG: {answer}\n"
        f"GIAI THICH: {expl[:200]}\n\n"
        f"Tieu chi:\n"
        f"- groundedness (1-5): Cau hoi va dap an co xuat phat tu doan tai lieu khong?\n"
        f"  (5=hoan toan tu tai lieu, 1=AI tu biet khong lien quan tai lieu)\n"
        f"- plausibility (1-5): Cac lua chon sai co hop ly, kho doan khong?\n"
        f"  (5=cac lua chon rat hop ly, 1=cac lua chon sai qua ro rang)\n\n"
        f"Tra ve JSON CHINH XAC, KHONG them gi khac:\n"
        f'{{"groundedness": <1-5>, "plausibility": <1-5>, "reasoning": "<ly do ngan gon>"}}'
    )

    try:
        raw = llm_service.chat_direct(
            prompt=judge_prompt,
            system_prompt="Ban la giam khao chat luong. Tra ve JSON dung dinh dang."
        )

        import re
        parsed = None
        try:
            parsed = json.loads(raw.strip())
        except Exception:
            m = re.search(r'\{.*?\}', raw, re.DOTALL)
            if m:
                try:
                    parsed = json.loads(m.group())
                except Exception:
                    pass

        if parsed and isinstance(parsed, dict):
            return {
                "groundedness": int(parsed.get("groundedness", 3)),
                "plausibility": int(parsed.get("plausibility", 3)),
                "reasoning":    str(parsed.get("reasoning", "")),
            }
    except Exception as e:
        print(f"  [WARN] Judge quiz parse loi: {e}")

    return {"groundedness": 0, "plausibility": 0, "reasoning": "Parse loi"}


def run_quiz_evaluation():
    """Chay danh gia toan bo tang Quiz Generation."""
    print("\n" + "="*60)
    print("  TANG 3: DANH GIA CHAT LUONG QUIZ")
    print("="*60)

    db = SessionLocal()
    llm_service = get_llm_service()

    try:
        doc_repo = DocumentRepository(db)
        docs = doc_repo.get_indexed()

        if not docs:
            print("[ERROR] Chua co tai lieu nao duoc indexed. Upload tai lieu truoc.")
            return

        print(f"[INFO] Tim thay {len(docs)} tai lieu da indexed.")

        # Chon tai lieu dau tien de danh gia
        doc = docs[0]
        print(f"[INFO] Dang danh gia tai lieu: '{doc.file_name}'")
        print("[INFO] Dang sinh 5 cau hoi quiz...")

        try:
            quiz_resp = generate_quiz(
                doc_id=doc.id,
                count=5,
                db=db,
                llm_service=llm_service,
                session_id="evaluator",
            )
        except Exception as e:
            print(f"[ERROR] Khong the sinh quiz: {e}")
            return

        questions = quiz_resp.questions
        print(f"[INFO] Sinh duoc {len(questions)} cau hoi. Bat dau cham diem...\n")

        # Lay cac chunks tu ChromaDB de so sanh
        chunks_map = {}
        try:
            chunk_ids = [q.chunk_id for q in questions if q.chunk_id]
            if chunk_ids:
                chunks = llm_service.get_chunks_by_ids(chunk_ids)
                chunks_map = {c.id: c.text for c in chunks}
        except Exception:
            pass

        results = []
        for i, q in enumerate(questions, 1):
            q_dict = {
                "question":    q.question,
                "options":     q.options,
                "answer":      q.answer,
                "explanation": q.explanation,
            }
            chunk_text = chunks_map.get(q.chunk_id, "Khong tim thay doan goc")

            print(f"[{i}/{len(questions)}] Cau: {q.question[:70]}...")

            scores = judge_quiz_question(llm_service, q_dict, chunk_text)
            overall = round((scores["groundedness"] + scores["plausibility"]) / 2, 2)
            status = "DAT" if overall >= QUALITY_THRESHOLD else "CHUA DAT"

            print(f"  Groundedness: {scores['groundedness']}/5 | "
                  f"Plausibility: {scores['plausibility']}/5 | "
                  f"Trung binh: {overall}/5 [{status}]")
            print(f"  Ly do: {scores['reasoning'][:100]}")
            print()

            results.append({
                "stt":           i,
                "question":      q.question[:120],
                "answer":        q.answer,
                "chunk_id":      q.chunk_id[:30] if q.chunk_id else "",
                "groundedness":  scores["groundedness"],
                "plausibility":  scores["plausibility"],
                "overall":       overall,
                "status":        status,
                "reasoning":     scores["reasoning"][:200],
            })

        # ── Tong ket ──
        valid = [r for r in results if r["overall"] > 0]
        if valid:
            avg_ground = round(sum(r["groundedness"] for r in valid) / len(valid), 2)
            avg_plaus  = round(sum(r["plausibility"]  for r in valid) / len(valid), 2)
            avg_overall = round(sum(r["overall"]      for r in valid) / len(valid), 2)
            pass_rate  = round(sum(1 for r in valid if r["status"] == "DAT") / len(valid) * 100, 1)

            print("="*60)
            print("  KET QUA TONG HOP - TANG 3 (QUIZ GENERATION)")
            print("="*60)
            print(f"  Groundedness (bam sat tai lieu):  {avg_ground}/5")
            print(f"  Plausibility (lua chon hop ly):    {avg_plaus}/5")
            print(f"  DIEM TRUNG BINH TONG:              {avg_overall}/5")
            print(f"  TY LE DAT (>= {QUALITY_THRESHOLD}/5):              {pass_rate}%")
            print()

            if avg_ground < 3:
                print("[CANH BAO] Groundedness thap - Cau hoi AI dang tu biet, khong tu tai lieu.")
                print("  -> Nen giam MAX_QUIZ_CONTENT_CHARS va tat CoT prompting de AI bam sat hon.")
            if avg_plaus < 3:
                print("[CANH BAO] Plausibility thap - Cac lua chon sai qua ro rang, de doan.")
                print("  -> Nen them vao prompt: 'Cac lua chon sai phai tuong tu nhau va hop ly'.")

        # Luu CSV
        out_file = PROJECT_ROOT / "evaluation_quiz.csv"
        with open(out_file, "w", newline="", encoding="utf-8-sig") as f:
            if results:
                writer = csv.DictWriter(f, fieldnames=results[0].keys())
                writer.writeheader()
                writer.writerows(results)
        print(f"\n[OK] Ket qua luu tai: {out_file}")

    finally:
        db.close()


if __name__ == "__main__":
    run_quiz_evaluation()
