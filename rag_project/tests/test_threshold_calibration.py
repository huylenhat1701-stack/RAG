"""
Test script to calibrate relevance thresholds for the new multilingual-e5-small model.
Run with: pytest tests/test_threshold_calibration.py -s -v
"""
import pytest
from backend.services.llm_service import LLMService

@pytest.fixture(scope="module")
def llm_service():
    return LLMService()

def test_calibrate_thresholds(llm_service):
    # 8 in-scope questions
    in_scope_qs = [
        "Làm thế nào để tìm cực trị của hàm nhiều biến?",
        "Vi phân toàn phần là gì?",
        "Trình bày phương pháp nhân tử Lagrange.",
        "Điều kiện đủ để hàm số có cực trị là gì?",
        "Tích phân bội hai được định nghĩa như thế nào?",
        "Đổi biến trong tích phân kép dùng Jacobian như thế nào?",
        "Tích phân đường loại 1 khác loại 2 ở điểm nào?",
        "Công thức Green liên hệ giữa tích phân đường và tích phân kép ra sao?"
    ]

    # 7 out-of-scope questions
    out_of_scope_qs = [
        "Cách nấu món phở bò Nam Định?",
        "Ai là tổng thống Mỹ năm 2024?",
        "Làm sao để code ReactJS nhanh hơn?",
        "Hướng dẫn chơi cờ vua cơ bản.",
        "Tại sao bầu trời màu xanh?",
        "Cách nuôi chó Husky khỏe mạnh.",
        "Quy định luật giao thông đường bộ mới nhất."
    ]

    in_scope_scores = []
    print("\n--- IN-SCOPE QUESTIONS ---")
    for q in in_scope_qs:
        results = llm_service.search(q, top_k=3)
        max_score = max((r.score for r in results), default=0.0)
        in_scope_scores.append(max_score)
        print(f"Q: {q}")
        print(f"Max Score: {max_score:.4f}")

    out_of_scope_scores = []
    print("\n--- OUT-OF-SCOPE QUESTIONS ---")
    for q in out_of_scope_qs:
        results = llm_service.search(q, top_k=3)
        max_score = max((r.score for r in results), default=0.0)
        out_of_scope_scores.append(max_score)
        print(f"Q: {q}")
        print(f"Max Score: {max_score:.4f}")

    # Calculate distributions
    if in_scope_scores:
        in_min, in_max, in_mean = min(in_scope_scores), max(in_scope_scores), sum(in_scope_scores)/len(in_scope_scores)
    else:
        in_min = in_max = in_mean = 0.0

    if out_of_scope_scores:
        out_min, out_max, out_mean = min(out_of_scope_scores), max(out_of_scope_scores), sum(out_of_scope_scores)/len(out_of_scope_scores)
    else:
        out_min = out_max = out_mean = 0.0

    print("\n" + "="*50)
    print("CALIBRATION RESULTS FOR E5 MODEL")
    print("="*50)
    print(f"IN-SCOPE      : Min={in_min:.4f}, Mean={in_mean:.4f}, Max={in_max:.4f}")
    print(f"OUT-OF-SCOPE  : Min={out_min:.4f}, Mean={out_mean:.4f}, Max={out_max:.4f}")
    print("="*50)

    # Make a rough suggestion
    suggested_no_context = out_max + 0.02
    suggested_relevance = in_min - 0.02 if in_min > suggested_no_context else suggested_no_context + 0.02
    
    print(f"SUGGESTED NO_CONTEXT_THRESHOLD: ~{suggested_no_context:.4f}")
    print(f"SUGGESTED RELEVANCE_THRESHOLD : ~{suggested_relevance:.4f}")
