# Triển khai thuật toán Adaptive Learning & CoT Math Tutor cho Smart Document Reader

Mục tiêu của kế hoạch này là nâng cấp hệ thống vượt trội hơn hẳn NotebookLM bằng cách tích hợp 2 thuật toán:
1. **Bayesian Knowledge Tracing (BKT)**: Dò tìm "lỗ hổng kiến thức", đánh giá năng lực của người dùng theo thời gian thực khi làm bài.
2. **Chain-of-Thought (CoT) Math Tutor**: Ép buộc LLM suy luận tính toán từng bước (Step-by-step) đối với các bài tập tính toán/Toán học, tránh tình trạng LLM sinh ra kết quả sai hoặc giải thích qua loa.

> [!IMPORTANT]
> **User Review Required**
> Do hệ thống chưa có cơ chế quản lý User (Đăng nhập/Đăng ký), tôi đề xuất sử dụng cơ chế **Anonymous Session ID** (hoặc mặc định là `user_1`) để lưu trữ lịch sử học tập. Người dùng hãy xác nhận có đồng ý với cách tiếp cận này cho bản thử nghiệm hay không?

## Open Questions
- Bạn muốn dùng Session ID lưu tạm trong bộ nhớ Frontend hay thêm 1 ô textbox để nhập "Tên người dùng"? (Trong plan tôi sẽ dùng giá trị mặc định là `"default_user"` để test nhanh).

---

## Proposed Changes

### Database Layer
Cần mở rộng cấu trúc SQLite để lưu trạng thái học tập của người dùng.

#### [MODIFY] backend/models/domain.py
- Thêm model `QuizHistory` lưu lịch sử từng câu trả lời: `session_id`, `doc_id`, `chunk_id`, `is_correct`, `timestamp`.
- Thêm model `UserKnowledge` lưu ma trận xác suất hiểu bài: `session_id`, `doc_id`, `chunk_id`, `probability` (xác suất hiểu bài, từ 0 đến 1).

#### [MODIFY] backend/db/database.py
- Import các model mới vào `init_db()` để SQLAlchemy tự động tạo bảng.

---

### Core Algorithm Service
Tạo một service mới đảm nhiệm logic toán học của BKT.

#### [NEW] backend/services/adaptive_tutor_service.py
- Lớp `AdaptiveTutorService`:
  - `update_knowledge(session_id, chunk_id, is_correct, db)`: Triển khai công thức BKT để tính toán lại xác suất hiểu bài $P(L)$ dựa trên kết quả trả lời đúng/sai.
  - `get_weak_chunks(session_id, doc_id, db)`: Trả về danh sách `chunk_id` có xác suất hiểu bài thấp (ví dụ: $< 0.6$).

---

### Integration with LLM, RAG & CoT Prompting

Thay đổi lớn nhất nằm ở đây. Chúng ta sẽ thay đổi cách lấy dữ liệu (RAG) và cách ra lệnh cho AI (Prompt) để nó giải Toán.

#### [MODIFY] backend/services/llm_service.py
- Thêm hàm `get_chunks_by_ids(chunk_ids)`: Truy vấn trực tiếp ChromaDB lấy nội dung của các chunk kiến thức bị yếu.
- Thêm hàm `get_random_chunks(filename, count)`: Truy vấn ngẫu nhiên chunks nếu người dùng chưa có dữ liệu yếu.

#### [MODIFY] backend/services/rag_service.py
- Cập nhật hàm `generate_quiz()`:
  1. Kiểm tra `adaptive_tutor_service` xem user có "weak chunks" nào không.
  2. Nếu có, fetch các weak chunks đó. Nếu không, fetch random chunks.
  3. Gán metadata `chunk_id` vào cấu trúc câu hỏi trả về.
- Cập nhật Prompt `_generate_quiz_batch` sử dụng kỹ thuật **Chain-of-Thought (CoT)**:
  - Bỏ yêu cầu `Giải thích: [giải thích ngắn]`.
  - Bắt buộc LLM phải sinh ra khối `<reasoning>` (suy luận từng bước công thức toán học) trước khi đưa ra `<answer>`.
  - Trả về JSON chứa `step_by_step_explanation` (sử dụng format LaTeX để Frontend render đẹp).

---

### API Endpoint & Frontend

#### [MODIFY] backend/api/routes.py
- Định nghĩa schema `QuizSubmitRequest` (session_id, chunk_id, is_correct).
- Tạo endpoint `POST /documents/{doc_id}/quiz/submit`: Nhận kết quả từ Frontend, gọi `AdaptiveTutorService` để cập nhật database.

#### [MODIFY] frontend/app.py
- Trong Tab "Bài Tập" (Quiz Competition), cập nhật logic khi user click nút đáp án (A/B/C/D):
  - Kiểm tra đúng/sai.
  - Gọi API `POST /documents/.../quiz/submit` ngầm để gửi kết quả lên Backend.
- Sửa giao diện `quiz-feedback` để hiển thị `step_by_step_explanation`:
  - Dùng `st.latex()` hoặc `st.markdown()` hỗ trợ MathJax/KaTeX để render công thức tính toán nhiều bước mà AI sinh ra.

---

## Verification Plan

### Automated Tests
1. Xóa file `rag.db` cũ hoặc để SQLAlchemy tự thêm bảng mới nếu hỗ trợ (hoặc viết script migration nhỏ).
2. Chạy lại FastAPI.

### Manual Verification
1. Upload một file PDF chứa **bài tập Toán hoặc Lý**.
2. Qua tab **Bài Tập**, tạo Quiz. Đảm bảo câu hỏi bám sát tài liệu.
3. Khi chọn đáp án (đúng hoặc sai), kiểm tra phần Giải thích xem nó có liệt kê **chi tiết tính toán từng bước (Step-by-step)** hay không, và công thức Toán có hiển thị chuẩn không.
4. Cố tình chọn **Sai** liên tục.
5. Tạo Quiz mới lần 2. Kiểm tra xem hệ thống có tự động lấy lại các kiến thức bị sai ở bài kiểm tra trước ra hỏi tiếp không.
