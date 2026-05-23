"""
=============================================================
TANG 1: Danh gia chat luong RAG (Q&A) bang LLM-as-a-Judge
=============================================================
Chay:
    cd rag_project
    python -m backend.scripts.evaluate_rag

Mo ta:
    - Tu dong sinh bo cau hoi mau tu ChromaDB (khong can ground truth thu cong)
    - Goi rag_service de lay cau tra loi
    - Dung chinh LLM cham diem theo 3 tieu chi: Faithfulness, Relevancy, Context Precision
    - In bao cao ket qua ra terminal va luu CSV
"""

import sys
import os
import json
import csv
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.db.database import SessionLocal
from backend.services.llm_service import get_llm_service
from backend.services.rag_service import answer_question
from backend.repositories.document_repo import DocumentRepository


# ─── Cau hoi mau co the tu chinh ────────────────────────────
SAMPLE_QUESTIONS = [
    "Noi dung chinh cua tai lieu la gi?",
    "Tai lieu de cap den nhung khai niem nao quan trong?",
    "Hay tom tat cac phan chinh trong tai lieu.",
    "Co nhung dinh nghia nao duoc neu trong tai lieu?",
    "Nhung diem noi bat nhat cua tai lieu la gi?",
]

# ─── Ngưỡng điểm đánh giá ─────────────────────────────────
SCORE_THRESHOLD = 3  # Tren 3/5 la dat


def generate_questions_from_chunks(llm_service, n=5):
    """
    Tu dong sinh bo cau hoi mau tu noi dung cac chunks trong ChromaDB.
    Khong can ground truth thu cong.
    """
    try:
        total = llm_service._collection.count()
        if total == 0:
            print("[WARN] ChromaDB trong - dung cau hoi mac dinh.")
            return SAMPLE_QUESTIONS

        # Lay ngau nhien mot so chunks
        sample_results = llm_service._collection.get(limit=min(n * 2, total))
        docs = sample_results.get("documents", [])
        if not docs:
            return SAMPLE_QUESTIONS

        import random
        selected = random.sample(docs, min(n, len(docs)))

        generated_qs = []
        for snippet in selected:
            prompt = (
                f"Dua vao doan van sau, hay dat ra 1 cau hoi hay, cu the va co the tra loi duoc tu doan van do.\n\n"
                f"Doan van:\n{snippet[:400]}\n\n"
                f"Chi tra ve cau hoi, khong them gi khac."
            )
            try:
                q = llm_service.chat_direct(
                    prompt=prompt,
                    system_prompt="Ban la giao vien. Dat cau hoi ngan gon, ro rang bang tieng Viet."
                ).strip()
                if q:
                    generated_qs.append(q)
            except Exception:
                pass

        return generated_qs if generated_qs else SAMPLE_QUESTIONS
    except Exception as e:
        print(f"[WARN] Khong the sinh cau hoi tu chunks: {e}")
        return SAMPLE_QUESTIONS


def judge_answer(llm_service, question: str, answer: str, context: str) -> dict:
    """
    Dung LLM-as-a-Judge cham diem cau tra loi theo 3 tieu chi.
    Tra ve dict: {faithfulness, relevancy, context_precision, overall, reasoning}
    """
    judge_prompt = (
        f"Ban la giam khao danh gia chat luong he thong Q&A. "
        f"Hay cham diem cau tra loi sau day theo 3 tieu chi (thang 1-5).\n\n"
        f"CAU HOI: {question}\n\n"
        f"NGU CANH (cac doan tai lieu da lay ra):\n{context[:800]}\n\n"
        f"CAU TRA LOI:\n{answer[:600]}\n\n"
        f"Hay tra ve JSON CHINH XAC theo mau sau, KHONG them gi khac:\n"
        f"{{\n"
        f'  "faithfulness": <1-5>,\n'
        f'  "relevancy": <1-5>,\n'
        f'  "context_precision": <1-5>,\n'
        f'  "reasoning": "<ly do ngan gon bang tieng Viet>"\n'
        f"}}"
    )

    try:
        raw = llm_service.chat_direct(
            prompt=judge_prompt,
            system_prompt="Ban la giam khao AI chat luong. Tra ve JSON dung dinh dang, khong them van ban."
        )

        # Parse JSON
        import re
        parsed = None
        try:
            parsed = json.loads(raw.strip())
        except Exception:
            m = re.search(r'\{.*?\}', raw, re.DOTALL)
            if m:
                parsed = json.loads(m.group())

        if parsed and isinstance(parsed, dict):
            return {
                "faithfulness":       int(parsed.get("faithfulness", 3)),
                "relevancy":          int(parsed.get("relevancy", 3)),
                "context_precision":  int(parsed.get("context_precision", 3)),
                "reasoning":          str(parsed.get("reasoning", "")),
            }
    except Exception as e:
        print(f"  [WARN] Judge parse loi: {e}")

    return {"faithfulness": 0, "relevancy": 0, "context_precision": 0, "reasoning": "Parse loi"}


def run_rag_evaluation():
    """Chay danh gia toan bo tang RAG."""
    print("\n" + "="*60)
    print("  TANG 1: DANH GIA CHAT LUONG RAG (Q&A)")
    print("="*60)

    db = SessionLocal()
    llm_service = get_llm_service()

    try:
        # Kiem tra co tai lieu chua
        doc_repo = DocumentRepository(db)
        docs = doc_repo.get_indexed()
        if not docs:
            print("[ERROR] Chua co tai lieu nao duoc indexed. Upload tai lieu truoc.")
            return

        print(f"[INFO] Tim thay {len(docs)} tai lieu da indexed.")
        print("[INFO] Dang sinh bo cau hoi mau tu ChromaDB...")

        questions = generate_questions_from_chunks(llm_service, n=5)
        print(f"[INFO] Chuan bi danh gia {len(questions)} cau hoi.\n")

        results = []
        for i, question in enumerate(questions, 1):
            print(f"[{i}/{len(questions)}] Cau hoi: {question[:70]}...")

            try:
                # Lay cau tra loi tu RAG
                resp = answer_question(
                    question=question,
                    top_k=5,
                    db=db,
                    llm_service=llm_service,
                )

                # Lay context tu sources
                context = f"Cac nguon: {[s.file_name for s in resp.sources]}"

                # Cham diem
                scores = judge_answer(
                    llm_service=llm_service,
                    question=question,
                    answer=resp.answer,
                    context=context,
                )

                overall = round((scores["faithfulness"] + scores["relevancy"] + scores["context_precision"]) / 3, 2)
                status = "DAT" if overall >= SCORE_THRESHOLD else "CHUA DAT"

                print(f"  Faithfulness: {scores['faithfulness']}/5 | "
                      f"Relevancy: {scores['relevancy']}/5 | "
                      f"Precision: {scores['context_precision']}/5 | "
                      f"Trung binh: {overall}/5 [{status}]")
                print(f"  Ly do: {scores['reasoning'][:100]}")
                print()

                results.append({
                    "question":          question,
                    "answer_preview":    resp.answer[:150],
                    "mode":              resp.mode,
                    "faithfulness":      scores["faithfulness"],
                    "relevancy":         scores["relevancy"],
                    "context_precision": scores["context_precision"],
                    "overall":           overall,
                    "status":            status,
                    "reasoning":         scores["reasoning"],
                })

            except Exception as e:
                print(f"  [ERROR] {e}\n")
                results.append({
                    "question": question, "answer_preview": "", "mode": "error",
                    "faithfulness": 0, "relevancy": 0, "context_precision": 0,
                    "overall": 0, "status": "LOI", "reasoning": str(e),
                })

        # ── Tong ket ──
        valid = [r for r in results if r["overall"] > 0]
        if valid:
            avg_faith  = round(sum(r["faithfulness"]      for r in valid) / len(valid), 2)
            avg_relev  = round(sum(r["relevancy"]          for r in valid) / len(valid), 2)
            avg_prec   = round(sum(r["context_precision"]  for r in valid) / len(valid), 2)
            avg_overall = round(sum(r["overall"]           for r in valid) / len(valid), 2)
            pass_rate  = round(sum(1 for r in valid if r["status"] == "DAT") / len(valid) * 100, 1)

            print("="*60)
            print("  KET QUA TONG HOP - TANG 1 (RAG Q&A)")
            print("="*60)
            print(f"  Faithfulness (khong bia dat):  {avg_faith}/5")
            print(f"  Relevancy (dung trong tam):     {avg_relev}/5")
            print(f"  Context Precision (ngu canh):   {avg_prec}/5")
            print(f"  DIEM TRUNG BINH TONG:           {avg_overall}/5")
            print(f"  TY LE DAT (>= {SCORE_THRESHOLD}/5):         {pass_rate}%")
            print()

            if avg_faith < 3:
                print("[CANH BAO] Faithfulness thap - AI co the dang bia dat thong tin.")
            if avg_relev < 3:
                print("[CANH BAO] Relevancy thap - Cau tra loi chua dung trong tam.")
            if avg_prec < 3:
                print("[CANH BAO] Context Precision thap - Nen tang top_k hoac chunk size.")

        # Luu CSV
        out_file = PROJECT_ROOT / "rag_project" / "evaluation_rag.csv"
        with open(out_file, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        print(f"\n[OK] Ket qua luu tai: {out_file}")

    finally:
        db.close()


if __name__ == "__main__":
    run_rag_evaluation()
