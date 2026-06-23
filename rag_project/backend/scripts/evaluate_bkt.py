"""
=============================================================
TANG 2: Danh gia do chinh xac cua thuat toan BKT
=============================================================
Chay:
    cd rag_project
    python -m backend.scripts.evaluate_bkt

Mo ta:
    - Lay lich su lam bai (QuizHistory) va xac suat hieu bai (UserKnowledge) tu DB
    - Neu chua co du lieu thuc te: tu dong tao Mock Data de demo
    - Tinh cac chi so: Accuracy, AUC-ROC, Log-Loss
    - In khuyen nghi dieu chinh tham so BKT (p_slip, p_guess, p_transit)
    - Luu ket qua ra CSV
"""

import sys
import csv
import random
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.db.database import SessionLocal
from backend.models.domain import QuizHistory, UserKnowledge


# ─── Tham so BKT hien tai (phai khop voi adaptive_tutor_service.py) ──
BKT_P_SLIP     = 0.1   # Xac suat lam sai du hieu bai
BKT_P_GUESS    = 0.2   # Xac suat doan mo dung du chua hieu
BKT_P_TRANSIT  = 0.1   # Xac suat hoc duoc kien thuc moi
BKT_THRESHOLD  = 60    # Nguong % de phan loai "hieu bai" vs "chua hieu"


def generate_mock_data(db, n_sessions=3, n_questions_each=10):
    """
    Tao du lieu gia lap neu DB chua co lich su thuc te.
    Moi session co xac suat hieu bai khac nhau.
    """
    print("[INFO] Tao Mock Data de demo...")
    mock_chunks = [f"chunk_mock_{i:03d}" for i in range(1, 21)]

    for s in range(n_sessions):
        session_id = f"mock_student_{s+1}"
        # Moi session co trinh do khac nhau
        base_prob = random.choice([0.3, 0.5, 0.75])

        for q in range(n_questions_each):
            chunk_id = random.choice(mock_chunks)
            # Xac suat tra loi dung phu thuoc vao trinh do
            is_correct = 1 if random.random() < base_prob else 0

            # Lay hoac tao UserKnowledge truoc khi tra loi
            uk = db.query(UserKnowledge).filter(
                UserKnowledge.session_id == session_id,
                UserKnowledge.chunk_id == chunk_id,
            ).first()

            if not uk:
                uk = UserKnowledge(
                    session_id=session_id,
                    doc_id=1,
                    chunk_id=chunk_id,
                    probability=50,
                )
                db.add(uk)
                db.flush()

            # Luu lich su
            history = QuizHistory(
                session_id=session_id,
                doc_id=1,
                chunk_id=chunk_id,
                is_correct=is_correct,
                timestamp=datetime.utcnow() - timedelta(minutes=random.randint(1, 60)),
            )
            db.add(history)

            # Cap nhat BKT
            p_L = uk.probability / 100.0
            if is_correct:
                num = p_L * (1 - BKT_P_SLIP)
                den = num + (1 - p_L) * BKT_P_GUESS
            else:
                num = p_L * BKT_P_SLIP
                den = num + (1 - p_L) * (1 - BKT_P_GUESS)
            p_L_obs = num / den if den > 0 else p_L
            p_L_new = p_L_obs + (1 - p_L_obs) * BKT_P_TRANSIT
            uk.probability = int(p_L_new * 100)

    db.commit()
    print(f"[OK] Da tao Mock Data: {n_sessions} session x {n_questions_each} cau hoi.")


def run_bkt_evaluation():
    """Chay danh gia toan bo tang BKT."""
    print("\n" + "="*60)
    print("  TANG 2: DANH GIA DO CHINH XAC CUA BKT")
    print("="*60)

    db = SessionLocal()

    try:
        # Kiem tra co du lieu chua
        total_history = db.query(QuizHistory).count()
        total_knowledge = db.query(UserKnowledge).count()

        print(f"[INFO] QuizHistory: {total_history} ban ghi | UserKnowledge: {total_knowledge} ban ghi")

        if total_history < 10:
            print("[INFO] Khong du du lieu thuc te, dang tao Mock Data...")
            generate_mock_data(db, n_sessions=3, n_questions_each=15)
            total_history = db.query(QuizHistory).count()
            total_knowledge = db.query(UserKnowledge).count()
            print(f"[INFO] Sau khi tao Mock: QuizHistory={total_history}, UserKnowledge={total_knowledge}\n")

        # ── Lay lich su lam bai ──────────────────────────────
        histories = db.query(QuizHistory).all()

        # Voi moi lan tra loi, lay BKT probability TRUOC khi tra loi
        # (Xap xi: lay gia tri hien tai trong UserKnowledge)
        uk_map = {}
        for uk in db.query(UserKnowledge).all():
            uk_map[(uk.session_id, uk.chunk_id)] = uk.probability

        y_true   = []  # Ket qua thuc te (0 hoac 1)
        y_prob   = []  # Xac suat BKT du doan
        y_pred   = []  # Du doan nhi phan (>= nguong thi du doan dung)
        details  = []

        for h in histories:
            bkt_prob = uk_map.get((h.session_id, h.chunk_id), 50)
            # Chuyen BKT probability thanh xac suat tra loi dung
            # P(correct) = P(know) * (1 - p_slip) + P(not_know) * p_guess
            p_know = bkt_prob / 100.0
            p_correct = p_know * (1 - BKT_P_SLIP) + (1 - p_know) * BKT_P_GUESS

            predicted_correct = 1 if bkt_prob >= BKT_THRESHOLD else 0

            y_true.append(h.is_correct)
            y_prob.append(round(p_correct, 4))
            y_pred.append(predicted_correct)

            details.append({
                "session_id":     h.session_id,
                "chunk_id":       h.chunk_id[:20],
                "bkt_probability": bkt_prob,
                "p_correct_pred":  round(p_correct, 3),
                "predicted":      predicted_correct,
                "actual":         h.is_correct,
                "correct_pred":   1 if predicted_correct == h.is_correct else 0,
            })

        # ── Tinh chi so ─────────────────────────────────────
        n = len(y_true)
        if n == 0:
            print("[ERROR] Khong co du lieu de danh gia.")
            return

        # Accuracy
        accuracy = sum(1 for p, a in zip(y_pred, y_true) if p == a) / n

        # AUC-ROC (tinh thu cong khong can sklearn)
        # Dung phuong phap thang so (Mann-Whitney U)
        pos = [p for p, a in zip(y_prob, y_true) if a == 1]
        neg = [p for p, a in zip(y_prob, y_true) if a == 0]

        auc = 0.5  # Default neu khong du du lieu
        if pos and neg:
            n_correct_pairs = sum(1 for p in pos for n_val in neg if p > n_val)
            n_tie_pairs = sum(1 for p in pos for n_val in neg if p == n_val)
            auc = (n_correct_pairs + 0.5 * n_tie_pairs) / (len(pos) * len(neg))

        # Log-Loss
        import math
        eps = 1e-9
        log_loss = -sum(
            a * math.log(max(p, eps)) + (1 - a) * math.log(max(1 - p, eps))
            for p, a in zip(y_prob, y_true)
        ) / n

        # ── In ket qua ──────────────────────────────────────
        print("="*60)
        print("  KET QUA TONG HOP - TANG 2 (BKT)")
        print("="*60)
        print(f"  Tong so lan tra loi da phan tich: {n}")
        print(f"  Accuracy (do chinh xac):           {accuracy:.1%}")
        print(f"  AUC-ROC (kha nang phan loai):      {auc:.3f}")
        print(f"  Log-Loss (sai lech xac suat):      {log_loss:.3f}")
        print()

        # Phan tich va khuyen nghi
        print("  PHAN TICH & KHUYEN NGHI:")
        if accuracy >= 0.75:
            print("  [TOT] Accuracy >= 75%: Mo hinh du doan on dinh.")
        elif accuracy >= 0.60:
            print("  [TRUNG BINH] Accuracy 60-75%: Co the cai thien bqng cach dieu chinh nguong BKT_THRESHOLD.")
        else:
            print("  [YEU] Accuracy < 60%: Nen xem lai tham so p_slip, p_guess, p_transit.")

        if auc >= 0.75:
            print("  [TOT] AUC-ROC >= 0.75: BKT phan biet gioi giua hieu vs chua hieu.")
        elif auc >= 0.60:
            print("  [TRUNG BINH] AUC-ROC 0.60-0.75: BKT phan biet kha.")
        else:
            print("  [YEU] AUC-ROC < 0.60: BKT gan nhu du doan ngau nhien. Tang p_transit hoac giam p_guess.")

        if log_loss <= 0.5:
            print("  [TOT] Log-Loss <= 0.5: Xac suat du doan sat voi thuc te.")
        elif log_loss <= 0.8:
            print("  [TRUNG BINH] Log-Loss 0.5-0.8: Xac suat co sai lech nho.")
        else:
            print("  [YEU] Log-Loss > 0.8: Xac suat BKT lech xa thuc te. Nen calibrate lai.")

        print()
        print(f"  Tham so BKT hien tai: p_slip={BKT_P_SLIP}, p_guess={BKT_P_GUESS}, p_transit={BKT_P_TRANSIT}")
        print(f"  Nguong phan loai: {BKT_THRESHOLD}%")

        # Luu CSV
        out_file = PROJECT_ROOT / "evaluation_bkt.csv"
        with open(out_file, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=details[0].keys())
            writer.writeheader()
            writer.writerows(details)

        # Luu summary
        summary_file = PROJECT_ROOT / "evaluation_bkt_summary.txt"
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write(f"Thoi diem danh gia: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Tong mau: {n}\n")
            f.write(f"Accuracy: {accuracy:.1%}\n")
            f.write(f"AUC-ROC:  {auc:.3f}\n")
            f.write(f"Log-Loss: {log_loss:.3f}\n")
            f.write(f"Tham so: p_slip={BKT_P_SLIP}, p_guess={BKT_P_GUESS}, p_transit={BKT_P_TRANSIT}\n")

        print(f"\n[OK] Chi tiet luu tai: {out_file}")
        print(f"[OK] Tom tat luu tai:  {summary_file}")

    finally:
        db.close()


if __name__ == "__main__":
    run_bkt_evaluation()
