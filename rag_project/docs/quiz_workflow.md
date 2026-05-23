# 📚 Workflow Tạo Bài Tập Trắc Nghiệm

## Tổng Quan

Tính năng **Thi Trắc Nghiệm** cho phép người dùng chọn một tài liệu đã upload,
AI sẽ tự động tạo bộ câu hỏi trắc nghiệm 4 lựa chọn (A/B/C/D) từ nội dung đó,
sau đó hiển thị dưới dạng giao diện thi tương tác — chọn đáp án, phản hồi ngay,
tính điểm, xem kết quả và xem lại chi tiết từng câu.

---

## Sơ Đồ Luồng Tổng Thể

```
[Người dùng]
  Chọn tài liệu + số câu (3–20)
  → Bấm "🚀 Bắt Đầu Thi"
        │
        ▼
[Frontend — app.py]
  POST /documents/{doc_id}/quiz  { "count": 10 }
        │
        ▼
[Backend — routes.py]
  create_quiz()
  Validate request → inject DB session + LLMService
        │
        ▼
[Backend — rag_service.py]
  generate_quiz()
  ┌─────────────────────────────────────────────┐
  │ 1. Lấy thông tin tài liệu từ DB             │
  │ 2. Đọc full text đã extract từ file         │
  │ 3. Truncate về 3.000 ký tự                  │
  │ 4. Vòng lặp batch (3 câu / lần gọi API)     │
  └─────────────────────────────────────────────┘
        │
        │  (lặp cho đến đủ số câu yêu cầu)
        ▼
[Backend — rag_service.py]
  _generate_quiz_batch()
  ┌─────────────────────────────────────────────┐
  │ Gửi prompt → LM Studio (Gemma 3 4B)         │
  │ Nhận text thô từ model                      │
  │ _clean_ai_preamble()  ← Làm sạch rác        │
  │ _try_parse_json()     ← Thử parse JSON      │
  │   └─ Thành công → dùng luôn                 │
  │   └─ Thất bại   ↓                           │
  │ _parse_text_format()  ← Parse text mẫu      │
  │   └─ _clean_question_text() trên mỗi câu    │
  │   └─ _parse_numbered_fallback() nếu lỗi     │
  └─────────────────────────────────────────────┘
        │
        ▼
[Backend]
  Ghép tất cả batch → QuizResponse
  { id, file_name, questions: [...], total, model_used }
        │
        ▼
[Frontend — app.py]
  Lưu vào st.session_state.quiz_questions
  Chuyển sang Phase "playing"
        │
        ▼
[Người dùng]
  Thi từng câu → Xem kết quả → Xem lại đáp án
```

---

## Chi Tiết Từng Bước

### 1. Đọc Nội Dung Tài Liệu

| Thành phần | Mô tả |
|---|---|
| **Hàm** | `get_document_content(doc_id, doc_repo)` trong `document_service.py` |
| **Nguồn dữ liệu** | File `.extracted.txt` — đã được bóc text sẵn từ PDF/DOCX khi upload |
| **Giới hạn** | Truncate cứng về **3.000 ký tự** để model nhỏ (Gemma 3 4B ~4.096 token) không bị tràn context |

> **Lý do truncate 3.000 ký tự:**
> - Model Gemma 3 4B có context window ~4.096 tokens
> - Prompt mẫu chiếm ~300 token
> - Câu trả lời dự kiến chiếm ~500 token/batch
> - Còn lại ~3.200 token ≈ 3.000 ký tự tiếng Việt để dành cho nội dung tài liệu

---

### 2. Batch 3 Câu / Lần

Thay vì yêu cầu 10 câu cùng lúc (model dễ bị lẫn lộn), hệ thống chia nhỏ:

```
count = 10 câu
batch_size = 3

Lần 1: tạo câu 1, 2, 3
Lần 2: tạo câu 4, 5, 6
Lần 3: tạo câu 7, 8, 9
Lần 4: tạo câu 10
```

**Ưu điểm batch nhỏ:**
- Model nhỏ tuân thủ format tốt hơn
- Dễ retry từng batch nếu lỗi
- Giảm nguy cơ vượt context window

---

### 3. Prompt Gửi Đến LM Studio

```
Đọc đoạn văn sau và tạo 3 câu hỏi trắc nghiệm (A/B/C/D).

VĂN BẢN:
[nội dung tài liệu, tối đa 2500 ký tự]

Viết kết quả theo mẫu sau, KHÔNG thêm gì khác:

Câu 1: [nội dung câu hỏi]
A. [lựa chọn A]
B. [lựa chọn B]
C. [lựa chọn C]
D. [lựa chọn D]
Đáp án: A
Giải thích: [giải thích ngắn]
```

**System prompt:** `"Bạn là giáo viên. Tạo câu hỏi trắc nghiệm bằng tiếng Việt theo đúng mẫu được yêu cầu."`

---

### 4. Fallback Parse 3 Lớp

Model nhỏ không phải lúc nào cũng trả về đúng format. Hệ thống thử lần lượt:

#### Lớp 1 — JSON Parse (`_try_parse_json`)
```
Nếu model trả về:
[{"id":1,"question":"...","options":{"A":"...","B":"..."},"answer":"A","explanation":"..."}]

→ json.loads() thành công → dùng luôn
```

#### Lớp 2 — Text Format Parse (`_parse_text_format`)
```
Nếu model trả về dạng text:
Câu 1: Đây là câu hỏi?
A. Lựa chọn A
B. Lựa chọn B
C. Lựa chọn C
D. Lựa chọn D
Đáp án: B
Giải thích: Vì...

→ Regex split theo "Câu N:" → parse từng block
```

#### Lớp 3 — Numbered Fallback (`_parse_numbered_fallback`)
```
Nếu text lộn xộn, không có "Câu N:":

→ Tìm dòng chứa dấu "?" (câu hỏi)
→ Tìm các dòng A./B./C./D. trong vòng 10 dòng kế tiếp
→ Tìm dòng "Đáp án:" nếu có
```

---

### 5. Làm Sạch Text Từ AI (`_clean_ai_preamble`, `_clean_question_text`)

Model nhỏ hay thêm "rác" vào response:

| Loại rác | Ví dụ | Xử lý |
|---|---|---|
| Lời xác nhận | "Tuyệt vời! Chúng ta sẽ..." | Bỏ toàn bộ text trước "Câu 1:" |
| Markdown bold | `**Câu 1:**` | `re.sub(r'\*\*(.+?)\*\*', r'\1', ...)` |
| Markdown italic | `*text*` | `re.sub(r'\*(.+?)\*', r'\1', ...)` |
| Prefix sót | "Câu 1: Nội dung..." | Strip prefix khỏi q_text |

---

### 6. Frontend — 3 Phase (Session State)

Trạng thái thi được lưu trong `st.session_state`:

```python
quiz_questions  = []      # Danh sách câu hỏi đã tạo
quiz_index      = 0       # Câu đang hiển thị (0-based)
quiz_score      = 0       # Số câu đúng tích lũy
quiz_answered   = {}      # {index: "A"/"B"/"C"/"D"} — câu đã trả lời
quiz_phase      = "setup" # "setup" | "playing" | "result"
quiz_doc_name   = ""      # Tên tài liệu đang thi
```

#### Phase 1 — Setup
- Người dùng chọn tài liệu, số câu
- Bấm "Bắt Đầu Thi" → gọi API → lưu câu hỏi vào session state → chuyển phase "playing"

#### Phase 2 — Playing
```
Hiển thị:
  [Header xanh: "🏆 Đang Thi" | Điểm X/Y]
  [Progress bar: %]
  [Card câu hỏi]
  [Nút A] [Nút B]
  [Nút C] [Nút D]

Sau khi chọn:
  → Highlight đúng = xanh ✅, sai = đỏ ❌
  → Hiện giải thích màu vàng
  → Nút "Câu tiếp →" hoặc "Xem Kết Quả"
```

#### Phase 3 — Result
```
Hiển thị:
  Trophy + Điểm % (màu vàng to)
  Xếp loại: Xuất Sắc / Giỏi / Khá / Cần Cố Gắng
  Thống kê: Đúng / Sai / Tổng

Nút hành động:
  [🔁 Thi Lại] [📋 Xem Lại Đáp Án] [🏠 Về Trang Chủ]
```

---

## Cấu Trúc Dữ Liệu

### QuizQuestion (Backend Schema)
```python
class QuizQuestion(BaseModel):
    id: int
    question: str                          # Nội dung câu hỏi
    options: dict                          # {"A": "...", "B": "...", "C": "...", "D": "..."}
    answer: str                            # "A" | "B" | "C" | "D"
    explanation: str = ""                  # Giải thích tại sao đúng
```

### QuizResponse (Backend Schema)
```python
class QuizResponse(BaseModel):
    id: int                                # ID tài liệu
    file_name: str                         # Tên file
    questions: List[QuizQuestion]          # Danh sách câu hỏi
    total: int                             # Tổng số câu
    model_used: str                        # Tên model LLM
```

---

## Các File Liên Quan

| File | Vai Trò |
|---|---|
| `frontend/app.py` | UI 3 phase (setup/playing/result), session state management |
| `backend/api/routes.py` | Endpoint `POST /documents/{id}/quiz` |
| `backend/services/rag_service.py` | Logic tạo quiz, batch, parse, clean |
| `backend/models/schemas.py` | `QuizQuestion`, `QuizResponse`, `QuizRequest` |
| `backend/services/document_service.py` | Đọc nội dung tài liệu đã extract |
| `backend/core/config.py` | `LLM_MAX_CONTENT_CHARS`, `CHUNK_SIZE`, ... |

---

## Điểm Cần Lưu Ý

> **Model nhỏ — chất lượng phụ thuộc vào tài liệu:**
> Gemma 3 4B hoạt động tốt nhất với tài liệu tiếng Anh hoặc tiếng Việt rõ ràng,
> cấu trúc mạch lạc. Tài liệu quá chuyên ngành hoặc dày đặc số liệu có thể
> sinh câu hỏi kém chất lượng.

> **Giới hạn 3.000 ký tự:**
> Tài liệu dài sẽ chỉ dùng 3.000 ký tự đầu để tạo câu hỏi. Có thể nâng lên
> nếu dùng model lớn hơn (ví dụ: Qwen 7B, Llama 3 8B).

> **Thời gian tạo:**
> 10 câu = 4 lần gọi API × ~15–30 giây/lần = **1–2 phút** tổng cộng.
