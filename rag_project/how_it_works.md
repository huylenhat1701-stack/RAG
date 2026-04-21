# Smart Document Reader — How It Works

> **Project:** Hệ thống Đọc Tài Liệu Thông Minh (RAG-based Q&A)
> **Authors:** Lê Nhật Huy — B23DCAT126 | Phạm Hải Đông — B23DCVT090
> **Tech Stack:** FastAPI + Streamlit + SQLite + LocalRAG + CodexOAuth (GPT-5)
> **Version:** 2.0.0

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   STREAMLIT FRONTEND                     │
│                   (app.py — port 8501)                  │
│  tabs: Quản lý | Đọc | Tóm tắt | Bài tập | Hỏi đáp    │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP / REST
                       ▼
┌─────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND                       │
│               (main.py + routes.py)                      │
│                  port 8000 /docs                        │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐      │
│  │ Routes   │→ │ Services │→ │   Repositories    │      │
│  │          │  │          │  │                    │      │
│  │ /docs/*  │  │ doc_svc  │  │  document_repo    │      │
│  │ /chat/*  │  │ rag_svc  │  │  history_repo     │      │
│  │          │  │ llm_svc  │  │                    │      │
│  └──────────┘  └──────────┘  └────────────────────┘      │
└──────────────────────┬──────────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
   ┌────────────┐ ┌──────────┐ ┌──────────────┐
   │  SQLite    │ │UPLOADS/  │ │ codex_oauth  │
   │   rag.db   │ │          │ │  _module/    │
   │            │ │  .pdf    │ │              │
   │ documents  │ │  .txt    │ │ LocalRAG     │
   │ chat_hist  │ │  .docx   │ │ CodexOAuth   │
   └────────────┘ └──────────┘ └──────────────┘
```

---

## 2. Data Flow — Full Pipeline

### 2.1 Upload & Index Pipeline

```
User uploads PDF/DOCX/TXT/MD
         │
         ▼
routes.py: POST /documents/upload
         │
         ├─ Validate extension (.pdf/.txt/.docx/.md)
         ├─ save_upload_file() → backend/uploads/{filename}
         ├─ DocumentRepository.create() → SQLite (status=UPLOADED)
         └─ BackgroundTasks.add_task(_process)
                    │
                    ▼
         document_service.process_and_index_document()
                    │
         ┌──────────┴──────────┐
         ▼                      ▼
   extract_document_text()    file → .extracted.txt
         │                          (if PDF/DOCX)
         ▼                          │
   text, page_count                 ▼
         │               llm_service.load_files_into_kb()
         │                          │
         ▼                          ▼
   LocalRAG.load_files() → chunks stored in RAM
         │
         ▼
   DocumentRepository.update_status(doc_id, "INDEXED", chunk_count=N)
         │
         ▼
   ✅ ChromaDB / in-memory index ready
```

### 2.2 Question Answering Pipeline (RAG Flow)

```
User asks: "Tóm tắt chương 3?"
         │
         ▼
routes.py: POST /chat/ask
         │
         ▼
rag_service.answer_question()
         │
         ├─ doc_repo.count_indexed() → check if docs exist
         ├─ llm_service.search(question, top_k)
         │         │
         │         ▼
         │   LocalRAG.search() → fuzzy matching
         │   Returns: List[SearchResult] (chunk + score)
         │         │
         └─ llm_service.generate_answer(question, context_chunks, history)
                    │
                    ▼
              CodexOAuth.chat()
              model=gpt-5.2-codex
              system_prompt=RAG_SYSTEM_PROMPT
                    │
                    ▼
              AI answer (grounded in retrieved chunks)
                    │
                    ▼
         history_repo.create(question, answer, sources)
                    │
                    ▼
         AskResponse(question, answer, sources[], model_used, history_id)
```

### 2.3 Summarize Pipeline

```
User clicks "Tóm tắt AI"
         │
         ▼
routes.py: POST /documents/{id}/summarize
         │
         ▼
rag_service.summarize_document()
         │
         ├─ doc_repo.get_by_id() → check doc exists
         ├─ doc.summary already exists? → return cached
         │         │
         │    (if not)
         │         ▼
         │   get_document_content() → read .extracted.txt or re-extract
         │         │
         │    (content truncated to 6000 chars)
         │         ▼
         └─ CodexOAuth.chat(system_prompt=SUMMARY_SYSTEM_PROMPT)
                    │
                    ▼
              doc_repo.update_summary(summary)
                    │
                    ▼
              DocumentSummaryResponse(id, file_name, summary, model)
```

### 2.4 Generate Exercise Pipeline

```
User selects "trắc nghiệm", count=5
         │
         ▼
routes.py: POST /documents/{id}/exercise
         │
         ▼
rag_service.generate_exercise()
         │
         ├─ get_document_content()
         ├─ build prompt: "TẠO TRẮC NGHIỆM TỪ: {filename}..."
         └─ CodexOAuth.chat(system_prompt=EDUCATIONAL_PROMPT)
                    │
                    ▼
              ExerciseResponse(id, file_name, exercise_text, model)
```

---

## 3. Database Schema (SQLite)

### Table: `documents`

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment ID |
| `file_name` | VARCHAR(255) | Original filename |
| `file_path` | VARCHAR(512) | Disk path to stored file |
| `file_size` | BIGINT | File size in bytes |
| `file_type` | VARCHAR(20) | pdf / txt / docx / md |
| `status` | VARCHAR(20) | UPLOADED / INDEXING / INDEXED / ERROR |
| `chunk_count` | INTEGER | Number of chunks indexed |
| `error_message` | TEXT | Error details if failed |
| `summary` | TEXT | AI-generated summary (cached) |
| `content_preview` | TEXT | First 500 characters |
| `page_count` | INTEGER | PDF page count (or estimate) |
| `uploaded_at` | DATETIME | Timestamp |

### Table: `chat_history`

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment ID |
| `question` | TEXT | User's question |
| `answer` | TEXT | AI's answer |
| `sources_json` | TEXT | JSON list of source filenames |
| `model_used` | VARCHAR(50) | LLM model (gpt-5.2-codex) |
| `created_at` | DATETIME | Timestamp |

---

## 4. API Endpoints

### Document Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/documents/upload` | Upload file, start background indexing |
| `GET` | `/api/v1/documents` | List all documents |
| `GET` | `/api/v1/documents/{id}/content` | Read full document text |
| `POST` | `/api/v1/documents/{id}/summarize` | AI summarize (cached) |
| `DELETE` | `/api/v1/documents/{id}` | Delete document + file |
| `GET` | `/api/v1/documents/{id}/download?source=original\|extracted` | Download file |
| `POST` | `/api/v1/documents/{id}/exercise` | Generate exercises |

### Chat / Q&A Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/chat/ask` | RAG question answering |
| `GET` | `/api/v1/chat/history` | Get chat history |
| `DELETE` | `/api/v1/chat/history` | Clear all history |

### System Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | System health check |
| `GET` | `/` | Root info |

---

## 5. Key Components

### 5.1 `LLMService` (Singleton)

```python
class LLMService:
    _codex: CodexOAuth     # Lazy-load on first call
    _rag: LocalRAG         # Lazy-load on first call
    _kb: LocalKnowledgeBase  # In-memory knowledge base

    Methods:
    ├── _get_codex()          → CodexOAuth client
    ├── _get_rag()            → LocalRAG instance
    ├── load_files_into_kb() → Index files into LocalRAG
    ├── reload_all_files()   → Reload on server restart
    ├── search(query, top_k) → Fuzzy search chunks
    ├── generate_answer()    → Call Codex with RAG context
    └── is_healthy()         → Return connection status
```

### 5.2 `CodexOAuth` (from `codex_oauth_module`)

- Authenticates via OAuth device flow
- Token stored in `~/.codex/auth.json`
- Login via: `python browser_login.py`
- Model: `gpt-5.2-codex` (configurable via `.env`)

### 5.3 `LocalRAG` (from `codex_oauth_module`)

- **Mode:** Fuzzy search (no embedding model needed — offline-capable)
- **Chunk config:** `chunk_size=1500`, `chunk_overlap=150`
- **Search:** `rag.search(kb, query, limit=N, min_score=0.1)`
- **Storage:** In-memory (no ChromaDB persistence for search)

### 5.4 Repository Pattern

```
routes.py
    ↓
services/ (business logic)
    ↓
repositories/ (data access)
    ↓
models/domain.py (SQLAlchemy ORM)
    ↓
db/database.py (SQLite + SessionLocal)
```

---

## 6. Lifecycle & Startup

### Application Startup (`lifespan` in `main.py`)

```
1. init_db()                → Create SQLite tables (documents, chat_history)
2. get_llm_service()        → Create LLMService singleton
3. reload_indexed_documents() → Re-load all INDEXED docs into LocalRAG
   (so knowledge base survives server restart)
4. FastAPI ready on port 8000
```

### Background Task (per document)

```
_process() runs in BackgroundTasks:
1. update_status("INDEXING")
2. extract_document_text(file_path, file_type)
3. update_content_preview(preview, page_count)
4. create .extracted.txt (for PDF/DOCX)
5. llm_service.load_files_into_kb([path])
6. update_status("INDEXED", chunk_count)
   OR on error → update_status("ERROR", error=...)
```

---

## 7. Document Status Flow

```
[File Uploaded]
     │
     ▼
  UPLOADED ──→ (background) ──→ INDEXING ──→ INDEXED ✅
     │                                    │
     │                                    └── chunk_count saved
     │
     └── error ──→ ERROR ❌
```

| Status | Meaning |
|---|---|
| `UPLOADED` | File saved, not yet processed |
| `INDEXING` | Background task extracting & chunking |
| `INDEXED` | Loaded into LocalRAG, ready for Q&A |
| `ERROR` | Processing failed, error_message logged |

---

## 8. File Structure

```
rag_project/
├── backend/
│   ├── main.py              # FastAPI app + lifespan
│   ├── core/
│   │   └── config.py        # .env config, prompts, paths
│   ├── api/
│   │   └── routes.py        # All REST endpoints
│   ├── services/
│   │   ├── document_service.py   # Extract + index pipeline
│   │   ├── rag_service.py        # Q&A, summarize, exercise
│   │   └── llm_service.py       # CodexOAuth + LocalRAG wrapper
│   ├── repositories/
│   │   ├── document_repo.py  # CRUD documents
│   │   └── history_repo.py  # CRUD chat_history
│   ├── models/
│   │   ├── domain.py        # SQLAlchemy tables
│   │   └── schemas.py       # Pydantic request/response
│   ├── db/
│   │   └── database.py      # SQLite engine + session
│   ├── uploads/            # Stored files + .extracted.txt
│   └── chroma_db/          # ChromaDB storage (unused in fuzzy mode)
├── frontend/
│   └── app.py              # Streamlit UI (6 tabs)
├── browser_login.py        # OAuth login script
├── check_token.py          # Token validation
└── start.bat               # Launch script (backend + frontend)
```

---

## 9. Configuration (`.env`)

```bash
# Codex OAuth
CODEX_CLIENT_ID=app_EMoamEEZ73f0CkXaXp7hrann
CODEX_AUTH_FILE=~/.codex/auth.json
CODEX_MODEL=gpt-5.2-codex
CODEX_REASONING_EFFORT=medium

# Storage
UPLOAD_DIR=backend/uploads
CHROMA_PERSIST_DIR=backend/chroma_db
DATABASE_URL=sqlite:///backend/rag.db

# RAG
CHUNK_SIZE=1500
CHUNK_OVERLAP=150
TOP_K_RESULTS=5
EMBEDDING_PROFILE=fast
```

---

## 10. Security & Notes

- **CORS:** `allow_origins=["*"]` — change in production
- **Auth token:** Stored at `~/.codex/auth.json`; re-login via `browser_login.py`
- **File validation:** Only `.pdf/.txt/.docx/.md` accepted; max 50MB
- **Path traversal:** `safe_filename` sanitized before saving
- **Token expiry:** LLMService auto-refreshes with 2-retry logic
- **No embedding model required** — fuzzy search is offline-capable