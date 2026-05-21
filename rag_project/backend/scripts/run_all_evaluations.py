"""
=============================================================
CHAY TOAN BO 3 TANG DANH GIA DO CHINH XAC
=============================================================
Chay:
    cd rag_project
    python -m backend.scripts.run_all_evaluations

Ket qua:
    - evaluation_rag.csv    (Tang 1: RAG Q&A)
    - evaluation_bkt.csv    (Tang 2: BKT chi tiet)
    - evaluation_bkt_summary.txt  (Tang 2: Tom tat)
    - evaluation_quiz.csv   (Tang 3: Quiz)
"""

import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    start = datetime.now()
    print("\n" + "="*60)
    print("  HE THONG DANH GIA DO CHINH XAC 3 TANG")
    print(f"  Bat dau luc: {start.strftime('%H:%M:%S %d/%m/%Y')}")
    print("="*60)

    results_summary = {}

    # ── TANG 2: BKT (chay truoc vi nhanh nhat, khong can LLM) ──
    print("\n[STEP 1/3] Dang chay Tang 2 (BKT)...")
    try:
        from backend.scripts.evaluate_bkt import run_bkt_evaluation
        run_bkt_evaluation()
        results_summary["BKT"] = "HOAN THANH"
    except Exception as e:
        print(f"[ERROR] Tang 2 that bai: {e}")
        results_summary["BKT"] = f"LOI: {str(e)[:80]}"

    # ── TANG 1: RAG Q&A (can LLM, mat nhieu thoi gian nhat) ──
    print("\n[STEP 2/3] Dang chay Tang 1 (RAG Q&A)...")
    try:
        from backend.scripts.evaluate_rag import run_rag_evaluation
        run_rag_evaluation()
        results_summary["RAG"] = "HOAN THANH"
    except Exception as e:
        print(f"[ERROR] Tang 1 that bai: {e}")
        results_summary["RAG"] = f"LOI: {str(e)[:80]}"

    # ── TANG 3: QUIZ (can LLM + tai lieu) ──
    print("\n[STEP 3/3] Dang chay Tang 3 (Quiz Quality)...")
    try:
        from backend.scripts.evaluate_quiz import run_quiz_evaluation
        run_quiz_evaluation()
        results_summary["QUIZ"] = "HOAN THANH"
    except Exception as e:
        print(f"[ERROR] Tang 3 that bai: {e}")
        results_summary["QUIZ"] = f"LOI: {str(e)[:80]}"

    # ── Bao cao cuoi ──
    end = datetime.now()
    elapsed = (end - start).seconds

    print("\n" + "="*60)
    print("  BAO CAO TONG KET CUOI CUNG")
    print("="*60)
    for layer, status in results_summary.items():
        icon = "OK" if status == "HOAN THANH" else "X"
        print(f"  [{icon}] Tang {layer}: {status}")

    print(f"\n  Tong thoi gian chay: {elapsed // 60} phut {elapsed % 60} giay")
    print(f"  Ket qua CSV xem trong thu muc: rag_project/")
    print("="*60)


if __name__ == "__main__":
    main()
