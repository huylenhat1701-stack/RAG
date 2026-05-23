# RAG - Smart Document Reader
Phần mềm hỗ trợ đọc tài liệu thông minh sử dụng kiến trúc RAG (Retrieval-Augmented Generation)

## Giới thiệu
- 📁 Upload và quản lý tài liệu (PDF, DOCX, TXT, MD)
- 🤖 Hỏi-đáp thông minh dựa trên nội dung tài liệu
- 📚 Tóm tắt tài liệu bằng AI
- 💬 Lịch sử hội thoại
- 🔍 Tìm kiếm ngữ nghĩa với ChromaDB

## Setup & Chạy

### 1. Chuẩn bị môi trường
```bash
cd rag_project
python -m venv .venv
.venv\Scripts\activate  # Windows
# hoặc: source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 2. Đăng nhập với OpenAI (Bước này QUAN TRỌNG)
```bash
python browser_login.py
```
- Sẽ mở trình duyệt tự động
- Đăng nhập với OpenAI account
- Token sẽ được lưu vào `~/.codex/auth.json`

### 3. Chạy ứng dụng

**Cách 1: Chạy cả backend và frontend (Windows)**
```bash
start.bat
```

**Cách 2: Chạy riêng rẽ**
```bash
# Terminal 1 - Backend FastAPI
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 - Frontend Streamlit
streamlit run frontend/app.py --server.port 8501
```

## Khắc phục sự cố

### Lỗi 500 - Token Error
Khi thấy lỗi "Token expired and refresh failed", hãy:

1. **Kiểm tra token**
   ```bash
   python check_token.py
   ```

2. **Đăng nhập lại**
   ```bash
   python browser_login.py
   ```

3. **Restart backend** (QUAN TRỌNG)
   - Dừng backend (Ctrl+C)
   - Chạy lại: `uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000`
   - Hoặc trên Windows: chạy `restart_backend.bat`

4. **Nếu vẫn lỗi - Reset toàn bộ token**
   ```bash
   python reset_token.py
   ```

### Lỗi File Not Found
- Kiểm tra tệp đã upload có nằm trong folder `uploads/` không
- Kiểm tra ChromaDB có được indexed không

### Lỗi Database
- Xóa file `rag.db` để reset database
- Xóa folder `chroma_db/` để reset vector store

## Kiến trúc

```
rag_project/
├── backend/              # FastAPI Backend
│   ├── main.py          # Ứng dụng chính
│   ├── api/routes.py    # Endpoints
│   ├── services/        # Business logic (LLM, RAG, Document)
│   ├── models/          # Database models
│   ├── db/              # Database setup
│   └── core/config.py   # Configuration
├── frontend/            # Streamlit Frontend
│   └── app.py
├── uploads/             # Folder lưu tài liệu
├── chroma_db/           # Vector database
└── requirements.txt     # Dependencies
```

## Công nghệ

- **Backend**: FastAPI + SQLAlchemy
- **Frontend**: Streamlit
- **AI/LLM**: CodexOAuth (GPT-5)
- **Vector Store**: ChromaDB + Sentence Transformers
- **Database**: SQLite

---

**Sinh viên**: Lê Nhật Huy - B23DCAT126 | Phạm Hải Đông - B23DCVT090

