 This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

  ---
  Project Overview

  Smart Document Reader — A RAG-based (Retrieval-Augmented Generation) document Q&A system built for university
   students.

  Authors: Lê Nhật Huy (B23DCAT126) | Phạm Hải Đông (B23DCVT090)
  Stack: FastAPI + ChromaDB + CodexOAuth (GPT-5) + Streamlit frontend

  Key features: Upload PDF/DOCX/TXT/MD → AI summarization → Intelligent Q&A → Exercise generation from
  documents

  ---
  Running the Project

  Backend API

  cd rag_project
  uvicorn backend.main:app --reload --port 8000
  - API docs: http://localhost:8000/docs
  - Health check: http://localhost:8000/api/v1/health

  Frontend (Streamlit)

  cd rag_project
  streamlit run frontend/app.py --server.port 8501

  First-Time Setup

  1. Run python browser_login.py to authenticate with Codex OAuth (saves to ~/.codex/auth.json)
  2. Backend auto-creates SQLite DB and reloads previously indexed documents on startup

  ---
  Architecture

  rag_project/
  ├── backend/
  │   ├── main.py              # FastAPI app, lifespan events, CORS, router registration
  │   ├── core/config.py       # .env config, Codex OAuth settings, chunk sizes, system prompts
  │   ├── db/database.py       # SQLite + SQLAlchemy engine, get_db dependency
  │   ├── models/
  │   │   ├── domain.py        # SQLAlchemy models: Document, ChatHistory
  │   │   └── schemas.py       # Pydantic request/response schemas
  │   ├── repositories/        # Repository pattern (DocumentRepository, HistoryRepository)
  │   ├── services/
  │   │   ├── document_service.py  # Upload, text extraction (PDF/DOCX/TXT), chunking pipeline
  │   │   ├── llm_service.py       # Singleton wrapping CodexOAuth + LocalRAG, ChromaDB integration
  │   │   └── rag_service.py       # answer_question(), summarize_document(), generate_exercise()
  │   └── api/routes.py        # All REST endpoints under /api/v1
  ├── frontend/app.py           # Streamlit UI
  ├── browser_login.py          # Codex OAuth login script
  ├── requirements.txt
  └── start.bat                 # Windows launcher

  ---
  Key Design Decisions

  Document Processing Pipeline

  Upload → Extract Text → Save .extracted.txt → LocalRAG.load_files() → ChromaDB index
  - Text extraction: PyMuPDF (PDF), python-docx (DOCX), raw read (TXT/MD)
  - Documents stored as .extracted.txt alongside originals for reload persistence
  - On server restart, reload_indexed_documents() re-loads all INDEXED documents into ChromaDB RAM

  LLM Service Singleton

  - LLMService is a single global instance managed via get_llm_service() dependency
  - CodexOAuth lazy-loads on first API call (requires ~/.codex/auth.json)
  - LocalRAG enables semantic search with ChromaDB (paraphrase-multilingual-MiniLM-L12-v2 embeddings)
  - codex_oauth_module is imported from the parent directory of rag_project (see sys.path manipulation in
  llm_service.py)

  Document Status Lifecycle

  UPLOADED → INDEXING → INDEXED | ERROR
  - Background task handles INDEXING via FastAPI BackgroundTasks
  - Only INDEXED docs are searchable via RAG

  Database

  - SQLite at backend/rag.db — two tables: documents, chat_history
  - sources stored as JSON string in chat_history.sources_json

  ---
  Important Paths

  ┌──────────────────┬────────────────────────────────┐
  │     Variable     │            Default             │
  ├──────────────────┼────────────────────────────────┤
  │ Codex auth file  │ ~/.codex/auth.json             │
  ├──────────────────┼────────────────────────────────┤
  │ Upload directory │ rag_project/backend/uploads/   │
  ├──────────────────┼────────────────────────────────┤
  │ ChromaDB persist │ rag_project/backend/chroma_db/ │
  ├──────────────────┼────────────────────────────────┤
  │ SQLite DB        │ rag_project/backend/rag.db     │
  └──────────────────┴────────────────────────────────┘

  Configurable via .env file (see backend/core/config.py).

  ---
  Supported File Types

  .pdf .txt .docx .md — max 50MB per file

  ---