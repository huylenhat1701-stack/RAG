# Giải thích chi tiết luồng nghiệp vụ và thuật toán của project RAG

Tài liệu này mô tả **đúng theo code hiện tại** của project `rag_project` (FastAPI + Streamlit + SQLite + ChromaDB + Local LLM).

---

## 1) Mục tiêu nghiệp vụ

Hệ thống giải quyết 4 nghiệp vụ chính:

1. **Quản lý tài liệu**: upload, lưu trữ, theo dõi trạng thái xử lý, xóa, tải lại file.
2. **Đọc nội dung tài liệu**: trích xuất text từ PDF/DOCX/TXT/MD và hiển thị.
3. **Hỏi đáp thông minh (RAG)**: trả lời dựa trên nội dung tài liệu đã nạp.
4. **Tóm tắt và tạo bài tập**: sinh nội dung học tập từ tài liệu.

---

## 2) Kiến trúc xử lý tổng quan

Luồng kiến trúc theo lớp:

`Frontend (Streamlit) -> API (FastAPI routes) -> Services (nghiệp vụ) -> Repositories (DB) -> SQLite/ChromaDB/FileSystem`

### Thành phần chính

- **Frontend**: `frontend/app.py`
  - Gọi API backend qua HTTP (`/api/v1/...`)
  - Chia tab theo nghiệp vụ: Tài Liệu, Đọc, Tóm Tắt, Bài Tập, Hỏi & Đáp, Lịch Sử

- **Backend API**: `backend/api/routes.py`
  - Nhận request, validate đầu vào, gọi service, trả response

- **Service layer**
  - `document_service.py`: lưu file, trích text, tạo file `.extracted.txt`, index Chroma
  - `rag_service.py`: điều phối Q&A, summarize, generate exercise
  - `llm_service.py`: quản lý LLM local + embedding + truy xuất ChromaDB + generate

- **Repository layer**
  - `document_repo.py`: CRUD bảng `documents`
  - `history_repo.py`: CRUD bảng `chat_history`

- **Data stores**
  - **SQLite**: metadata tài liệu + lịch sử hỏi đáp
  - **ChromaDB**: lưu vector embedding các chunk
  - **Filesystem**: file upload gốc + file text trích xuất

---

## 3) Mô hình dữ liệu nghiệp vụ

### Bảng `documents`

Theo dõi vòng đời mỗi tài liệu:
- `UPLOADED`: đã nhận file
- `INDEXING`: đang xử lý/trích xuất/chunk/embed
- `INDEXED`: đã sẵn sàng cho tìm kiếm RAG
- `ERROR`: xử lý lỗi, có `error_message`

Thông tin quan trọng:
- `file_name`, `file_path`, `file_type`, `file_size`
- `chunk_count`
- `content_preview` (500 ký tự đầu)
- `page_count`
- `summary` (cache tóm tắt đã sinh)

### Bảng `chat_history`

Lưu lại phiên hỏi đáp:
- `question`, `answer`
- `sources_json` (danh sách file nguồn)
- `model_used`
- `created_at`

---

## 4) Luồng nghiệp vụ chi tiết

### 4.1 Upload và index tài liệu

### Bước API
Endpoint: `POST /api/v1/documents/upload`

1. Kiểm tra extension hợp lệ: `.pdf`, `.txt`, `.docx`, `.md`
2. Lưu file vào `UPLOAD_DIR`
3. Kiểm tra kích thước <= 50MB
4. Tạo bản ghi DB trạng thái `UPLOADED`
5. Chạy background task `_process()` để xử lý index

### Bước background xử lý
Hàm: `process_and_index_document(...)`

1. Update trạng thái `INDEXING`
2. Trích xuất text theo loại file:
   - PDF: PyMuPDF
   - DOCX: python-docx
   - TXT/MD: đọc text trực tiếp
3. Làm sạch text (xóa ký tự `NUL`) để tránh lỗi SQLite/Chroma
4. Lưu `content_preview` + `page_count`
5. Nếu PDF/DOCX -> tạo thêm file `.extracted.txt`
6. Chunk + embedding + add vào Chroma collection
7. Update trạng thái `INDEXED`, lưu `chunk_count`
8. Nếu lỗi -> chuyển `ERROR`, lưu `error_message`

---

### 4.2 Đọc nội dung tài liệu

Endpoint: `GET /api/v1/documents/{id}/content`

Luồng:
1. Tìm doc theo `id`
2. Ưu tiên đọc file `.extracted.txt` nếu có
3. Nếu chưa có thì trích xuất từ file gốc
4. Trả về:
   - `content`
   - `word_count`
   - `char_count`
   - `page_count`

Ý nghĩa nghiệp vụ: người dùng có thể đọc nội dung sạch đã chuẩn hóa mà không phụ thuộc định dạng ban đầu.

---

### 4.3 Hỏi đáp tài liệu (Q&A) với cơ chế chọn mode

Endpoint: `POST /api/v1/chat/ask`
Hàm điều phối: `answer_question(...)`

### Bước 1: Xác định tập tài liệu được phép truy vấn
- Nếu user chọn `doc_ids` -> chỉ truy vấn trong danh sách đó
- Nếu không chọn -> dùng tất cả doc trạng thái `INDEXED`

### Bước 2: Thử ghép full content
- Đọc toàn bộ nội dung từng tài liệu đã chọn
- Nếu nhiều tài liệu, thêm header phân tách theo file
- Tính tổng số ký tự `combined_content`

### Bước 3: Quyết định thuật toán

#### Mode A — `full_context`
Điều kiện: tổng content <= `FULL_CONTEXT_THRESHOLD_CHARS`

- Đưa **toàn bộ nội dung** vào prompt
- Gọi `generate_answer_full_context`
- Nguồn trích dẫn: tất cả file đã đưa vào context (score 1.0)

#### Mode B — `rag`
Điều kiện: tài liệu quá dài

- Vector search trong Chroma: `llm_service.search(question, top_k, allowed_filenames)`
- Lấy danh sách chunk liên quan nhất
- Gọi `generate_answer` với context là các chunk
- Xây dựng danh sách nguồn từ chunk tìm được (kèm relevance score)

### Bước 4: Lưu lịch sử
- Ghi `question`, `answer`, `sources`, `model_used` vào `chat_history`
- Trả `mode` và `context_chars` để frontend hiển thị badge

---

### 4.4 Tóm tắt tài liệu

Endpoint: `POST /api/v1/documents/{id}/summarize`
Hàm: `summarize_document(...)`

Luồng:
1. Lấy tài liệu theo ID
2. Nếu đã có `summary` trong DB -> trả cache ngay
3. Lấy content tài liệu
4. Nếu content <= `LLM_MAX_CONTENT_CHARS`:
   - Tóm tắt trực tiếp 1 lần
5. Nếu content quá dài:
   - Chia thành nhiều segment
   - Tóm tắt từng segment
   - Tổng hợp các tóm tắt con thành bản cuối
6. Lưu `summary` vào DB để dùng lại

Ý nghĩa: vừa tối ưu tốc độ (cache), vừa xử lý được tài liệu dài.

---

### 4.5 Tạo bài tập từ tài liệu

Endpoint: `POST /api/v1/documents/{id}/exercise`
Hàm: `generate_exercise(...)`

Luồng:
1. Lấy content tài liệu
2. Cắt an toàn theo giới hạn context (`_safe_truncate`)
3. Tạo prompt theo `exercise_type` và `count`
4. Gọi LLM sinh bài tập
5. Trả `exercise_text`

---

## 5) Thuật toán cốt lõi

### 5.1 Thuật toán chunking văn bản

Hàm: `_chunk_text(text, filename)`

- Tách văn bản theo từ (`split()`)
- Dùng cửa sổ trượt:
  - `CHUNK_SIZE` (mặc định 600 từ)
  - `CHUNK_OVERLAP` (mặc định 80 từ)
- `step = CHUNK_SIZE - CHUNK_OVERLAP`
- Mỗi chunk có `id`, `text`, `filename`

Mục đích:
- Giữ ngữ cảnh liên tục giữa các chunk nhờ overlap
- Tối ưu truy xuất khi tìm đoạn liên quan

### 5.2 Thuật toán embedding + retrieval

### Index
1. Dùng model `SentenceTransformer` tạo embedding cho từng chunk
2. Lưu vào Chroma collection cùng metadata `filename`

### Search
1. Embed query
2. Query Chroma theo `top_k`
3. Có thể lọc theo `allowed_filenames`
4. Chuyển `distance` -> `score` theo công thức:
   - `score = 1 / (1 + distance)`

Kết quả: danh sách `SearchResult(chunk, score)`

### 5.3 Thuật toán chọn Full-Context vs RAG

Đây là điểm chính của project:

- Nếu dữ liệu đủ nhỏ: **ưu tiên Full-Context** để tăng độ đầy đủ
- Nếu dữ liệu lớn: **chuyển RAG** để giảm tải context và vẫn đảm bảo liên quan

Tiêu chí chọn dựa trên tổng số ký tự tài liệu so với ngưỡng.

---

## 6) Quản lý context window và an toàn khi gọi LLM

`LLMService` có các cơ chế:

1. Tự detect context window model qua endpoint `/models`
2. Tính `max_output_tokens` và `max_content_chars` an toàn
3. `_safe_truncate(...)` chỉ cắt khi vượt ngưỡng thực tế
4. HTTP timeout rõ ràng (connect/read/write/pool)
5. Bắt lỗi kết nối, timeout, lỗi HTTP và trả thông báo nghiệp vụ

---

## 7) Luồng khởi động hệ thống

Tại `backend/main.py` (lifespan):

1. `init_db()` tạo bảng SQLite nếu chưa có
2. Khởi tạo singleton `LLMService`
3. `reload_indexed_documents(...)`:
   - lấy tất cả tài liệu `INDEXED`
   - ưu tiên nạp `.extracted.txt`
   - đồng bộ danh sách file cho knowledge base khi server restart

Mục tiêu: hệ thống lên là dùng được ngay với dữ liệu đã xử lý trước đó.

---

## 8) Các điểm xử lý lỗi và biên quan trọng

- Chưa có tài liệu index -> Q&A trả phản hồi hướng dẫn upload
- File quá lớn (>50MB) -> từ chối upload
- File không hỗ trợ -> trả lỗi 400
- Lỗi parse PDF/DOCX -> trạng thái `ERROR`, có message
- Không kết nối được local LLM -> health báo warning/offline
- Context quá dài -> truncate có chú thích cho người dùng

---

## 9) Tóm tắt ngắn vòng đời một câu hỏi

1. User đặt câu hỏi ở tab Hỏi & Đáp
2. Frontend gửi `question`, `top_k`, `history`, `doc_ids`
3. Backend chọn mode `full_context` hoặc `rag`
4. LLM sinh câu trả lời dựa trên tài liệu
5. Backend lưu lịch sử và trả kết quả + nguồn trích dẫn
6. Frontend hiển thị badge mode và nguồn

---

## 10) Kết luận

Project được thiết kế theo hướng:
- Tách lớp rõ ràng (API / Service / Repository)
- Kết hợp **Full-Context** và **RAG retrieval** linh hoạt
- Dễ mở rộng cho các nghiệp vụ học tập (tóm tắt, bài tập, hỏi đáp)
- Tối ưu trải nghiệm người dùng với xử lý nền, cache summary, và lịch sử hội thoại
