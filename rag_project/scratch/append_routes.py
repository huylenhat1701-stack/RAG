import sys
sys.stdout.reconfigure(encoding='utf-8')

path = r'c:\project\new\RAG\rag_project\backend\api\routes.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

new_code = '''
# ============================================================
# HEALTH CHECK
# ============================================================

@router.get(
    "/health",
    summary="Kiem tra he thong",
    tags=["He thong"],
)
def health_check(llm_service: LLMService = Depends(get_llm_service)):
    """Kiem tra trang thai ket noi Local LLM va RAG."""
    status = llm_service.is_healthy()
    return {
        "status": "ok" if status.get("codex_connected") else "warning",
        **status,
    }


# ============================================================
# EVALUATION ENDPOINTS
# ============================================================

@router.get(
    "/evaluate/bkt",
    summary="Lay chi so danh gia BKT tu database",
    tags=["Danh gia"],
)
def get_bkt_stats(db: Session = Depends(get_db)):
    """
    Lay thong ke BKT tu database:
    - Tong so session, tong so lan tra loi
    - Phan phoi diem BKT (thap/trung/cao)
    - Accuracy du doan cua thuat toan BKT
    - Ty le dung/sai theo tung muc BKT
    """
    import math
    from ..models.domain import QuizHistory, UserKnowledge

    BKT_P_SLIP = 0.1
    BKT_P_GUESS = 0.2
    BKT_THRESHOLD = 60

    histories = db.query(QuizHistory).all()
    knowledges = db.query(UserKnowledge).all()

    total_answers = len(histories)
    total_sessions = len(set(h.session_id for h in histories))
    total_chunks_tracked = len(knowledges)

    # Phan phoi BKT score
    low_pct    = sum(1 for k in knowledges if k.probability < 40)
    mid_pct    = sum(1 for k in knowledges if 40 <= k.probability < 70)
    high_pct   = sum(1 for k in knowledges if k.probability >= 70)

    # Accuracy: lay tung record, so sanh du doan vs thuc te
    uk_map = {(k.session_id, k.chunk_id): k.probability for k in knowledges}
    correct_preds = 0
    y_true_all = []
    y_prob_all = []

    for h in histories:
        bkt_prob = uk_map.get((h.session_id, h.chunk_id), 50)
        predicted = 1 if bkt_prob >= BKT_THRESHOLD else 0
        if predicted == h.is_correct:
            correct_preds += 1
        p_know = bkt_prob / 100.0
        p_correct = p_know * (1 - BKT_P_SLIP) + (1 - p_know) * BKT_P_GUESS
        y_true_all.append(h.is_correct)
        y_prob_all.append(p_correct)

    accuracy = round(correct_preds / total_answers, 4) if total_answers > 0 else 0

    # AUC-ROC thu cong
    pos = [p for p, a in zip(y_prob_all, y_true_all) if a == 1]
    neg = [p for p, a in zip(y_prob_all, y_true_all) if a == 0]
    auc = 0.5
    if pos and neg:
        n_correct_pairs = sum(1 for p in pos for n_val in neg if p > n_val)
        n_tie_pairs = sum(1 for p in pos for n_val in neg if p == n_val)
        auc = (n_correct_pairs + 0.5 * n_tie_pairs) / (len(pos) * len(neg))

    # Log-Loss
    eps = 1e-9
    log_loss = 0.0
    if y_prob_all:
        log_loss = -sum(
            a * math.log(max(p, eps)) + (1 - a) * math.log(max(1 - p, eps))
            for p, a in zip(y_prob_all, y_true_all)
        ) / len(y_true_all)

    # Accuracy theo nhom BKT
    group_stats = {"low": {"correct": 0, "total": 0}, "mid": {"correct": 0, "total": 0}, "high": {"correct": 0, "total": 0}}
    for h in histories:
        bkt_prob = uk_map.get((h.session_id, h.chunk_id), 50)
        if bkt_prob < 40:
            g = "low"
        elif bkt_prob < 70:
            g = "mid"
        else:
            g = "high"
        group_stats[g]["total"] += 1
        if h.is_correct:
            group_stats[g]["correct"] += 1

    group_accuracy = {}
    for g, s in group_stats.items():
        group_accuracy[g] = round(s["correct"] / s["total"], 3) if s["total"] > 0 else 0

    return {
        "total_answers":       total_answers,
        "total_sessions":      total_sessions,
        "total_chunks_tracked": total_chunks_tracked,
        "accuracy":            round(accuracy, 3),
        "auc_roc":             round(auc, 3),
        "log_loss":            round(log_loss, 3),
        "distribution": {
            "low_count":   low_pct,
            "mid_count":   mid_pct,
            "high_count":  high_pct,
        },
        "group_accuracy": group_accuracy,
        "correct_total":  sum(h.is_correct for h in histories),
        "wrong_total":    sum(1 - h.is_correct for h in histories),
    }


@router.get(
    "/evaluate/rag-stats",
    summary="Lay thong ke chat luong RAG tu lich su hoi dap",
    tags=["Danh gia"],
)
def get_rag_stats(db: Session = Depends(get_db)):
    """
    Phan tich lich su hoi dap trong ChatHistory de tao thong ke RAG co ban:
    - Tong so cau hoi, phan bo mode (full_context vs rag)
    - Trung binh chieu dai cau tra loi
    """
    from ..models.domain import ChatHistory

    histories = db.query(ChatHistory).all()
    total = len(histories)
    if total == 0:
        return {"total_questions": 0, "message": "Chua co lich su hoi dap nao."}

    avg_answer_len = round(sum(len(h.answer) for h in histories) / total)
    avg_question_len = round(sum(len(h.question) for h in histories) / total)

    # Phan tich nguon (sources)
    multi_source = 0
    for h in histories:
        try:
            import json as _json
            srcs = _json.loads(h.sources_json) if h.sources_json else []
            if len(srcs) > 1:
                multi_source += 1
        except Exception:
            pass

    return {
        "total_questions":     total,
        "avg_answer_length":   avg_answer_len,
        "avg_question_length": avg_question_len,
        "multi_source_answers": multi_source,
        "multi_source_pct":    round(multi_source / total * 100, 1) if total > 0 else 0,
    }
'''

with open(path, 'a', encoding='utf-8') as f:
    f.write(new_code)

print("OK - Appended evaluation endpoints")
