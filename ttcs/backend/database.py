from datetime import datetime, timezone
import os
import sqlite3
from typing import List, Optional

import config

try:
    from models import DocumentRecord
except ImportError:
    from backend.models import DocumentRecord


DATABASE_PATH = config.DATABASE_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                status TEXT DEFAULT 'UPLOADED',
                created_at TEXT NOT NULL,
                chunk_count INTEGER DEFAULT 0
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                sources TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def insert_document(doc: DocumentRecord) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO documents (id, filename, file_type, status, created_at, chunk_count)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (doc.id, doc.filename, doc.file_type, doc.status.value, doc.created_at, doc.chunk_count),
        )
        conn.commit()
    finally:
        conn.close()


def update_document_status(doc_id: str, status: str, chunk_count: int = 0) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE documents SET status = ?, chunk_count = ? WHERE id = ?",
            (status, chunk_count, doc_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_all_documents() -> List[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM documents").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_document_by_id(doc_id: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_document(doc_id: str) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()
    finally:
        conn.close()


def insert_chat_history(question: str, answer: str, sources_json: str) -> None:
    conn = get_connection()
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT INTO chat_history (question, answer, sources, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (question, answer, sources_json, timestamp),
        )
        conn.commit()
    finally:
        conn.close()


def get_chat_history(limit: int = 50) -> List[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM chat_history ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
