# Hướng Dẫn: Adaptive Learning & CoT Math Tutor

Thuật toán Bayesian Knowledge Tracing (BKT) và phương pháp prompting Chain-of-Thought (CoT) đã được tích hợp thành công vào hệ thống Smart Document Reader. Dưới đây là tóm tắt những thay đổi chính:

## 1. Cơ Sở Dữ Liệu (Database Layer)
- Đã thêm hai bảng mới vào `backend/models/domain.py`:
  - `QuizHistory`: Lưu lại lịch sử trả lời câu hỏi (Đúng/Sai) cho từng phần kiến thức (`chunk_id`).
  - `UserKnowledge`: Lưu trữ xác suất hiểu bài (từ 0 đến 100%) của người dùng đối với từng `chunk_id`.
- Cập nhật `backend/db/database.py` để tự động khởi tạo các bảng này khi chạy hệ thống.

## 2. Core Algorithm (Thuật toán BKT)
- Đã tạo `backend/services/adaptive_tutor_service.py` chứa lớp `AdaptiveTutorService`.
- Hệ thống áp dụng các công thức BKT để tính toán xác suất thực sự hiểu bài của người dùng sau mỗi lần trả lời.
- Có khả năng lấy ra các "weak chunks" (những đoạn kiến thức mà hệ thống đánh giá người dùng có xác suất hiểu < 60%).

## 3. RAG & LLM Integration (CoT & Adaptive Fetching)
- Cập nhật `backend/services/llm_service.py` thêm hàm `get_chunks_by_ids` (để query các chunks yếu) và `get_random_chunks` (khi chưa có dữ liệu điểm yếu).
- Sửa đổi `generate_quiz` trong `backend/services/rag_service.py`:
  - Nếu người dùng có "weak chunks", RAG sẽ ưu tiên nhắm vào các chunks này để tạo bộ câu hỏi thi thay vì lấy ngẫu nhiên.
  - Áp dụng **Chain-of-Thought (CoT)** trong prompt sinh câu hỏi: Bắt buộc LLM phải trả về một khối `<reasoning>` trước khi đưa ra `<answer>`, giúp AI giải thích từng bước (step-by-step) đối với các bài toán.

## 4. API & Frontend
- Thêm endpoint `POST /documents/{doc_id}/quiz/submit` vào `backend/api/routes.py` để frontend có thể gửi kết quả trả lời của người dùng.
- Giao diện bài tập (`frontend/app.py`):
  - Ẩn gọi API submit mỗi khi người dùng click vào một đáp án (A/B/C/D).
  - Tích hợp thêm phần hiển thị **Bước giải chi tiết (CoT)** sinh ra bởi AI bên cạnh giải thích ngắn.

> [!TIP]
> Bạn có thể chạy lại server FastAPI ngay bây giờ để test. Do dùng SQLite và SQLAlchemy `create_all`, các bảng mới sẽ tự động được thêm vào DB cũ (nếu cấu trúc tương thích) hoặc bạn có thể xóa file `rag.db` đi để khởi tạo lại từ đầu nếu gặp lỗi schema.

## Kiểm tra hệ thống:
1. Chạy Backend và Frontend.
2. Upload một tài liệu Toán hoặc Lý.
3. Chuyển sang Tab "Bài Tập" và bắt đầu thi. 
4. Trả lời một vài câu (cố tình sai).
5. Thi lại tài liệu đó, hệ thống BKT sẽ phân tích và tạo ra các câu hỏi xoáy vào kiến thức bạn vừa làm sai. Đồng thời hãy xem phần "Bước giải chi tiết" để thấy sức mạnh của CoT!
