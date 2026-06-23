"""
Migration script: Thêm các cột còn thiếu vào bảng hiện có
và tạo các bảng mới nếu chưa có.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "rag.db")

def get_existing_columns(conn, table_name):
    cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {col[1] for col in cols}

def get_existing_tables(conn):
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {t[0] for t in tables}

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    tables = get_existing_tables(conn)
    print(f"[INFO] Bảng hiện có: {tables}")

    # ============================================================
    # 1. Tạo bảng users nếu chưa có
    # ============================================================
    if "users" not in tables:
        print("[MIGRATE] Tạo bảng users...")
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(100) NOT NULL UNIQUE,
                hashed_password VARCHAR(255) NOT NULL,
                full_name VARCHAR(200) DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        print("[OK] Tạo bảng users xong.")
    else:
        print("[SKIP] Bảng users đã tồn tại.")

    # ============================================================
    # 2. Thêm cột user_id vào documents nếu chưa có
    # ============================================================
    if "documents" in tables:
        cols = get_existing_columns(conn, "documents")
        print(f"[INFO] Cột hiện có trong documents: {cols}")
        if "user_id" not in cols:
            print("[MIGRATE] Thêm cột user_id vào documents...")
            cursor.execute("ALTER TABLE documents ADD COLUMN user_id INTEGER REFERENCES users(id)")
            conn.commit()
            print("[OK] Thêm user_id xong.")
        else:
            print("[SKIP] Cột user_id đã tồn tại trong documents.")
    else:
        print("[INFO] Bảng documents chưa có, SQLAlchemy sẽ tạo tự động.")

    # ============================================================
    # 3. Tạo bảng chat_history nếu chưa có
    # ============================================================
    if "chat_history" not in tables:
        print("[MIGRATE] Tạo bảng chat_history...")
        cursor.execute("""
            CREATE TABLE chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id),
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                sources_json TEXT,
                model_used VARCHAR(50),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        print("[OK] Tạo bảng chat_history xong.")
    else:
        cols = get_existing_columns(conn, "chat_history")
        if "user_id" not in cols:
            print("[MIGRATE] Thêm cột user_id vào chat_history...")
            cursor.execute("ALTER TABLE chat_history ADD COLUMN user_id INTEGER REFERENCES users(id)")
            conn.commit()
        print("[SKIP] Bảng chat_history đã tồn tại.")

    # ============================================================
    # 4. Tạo bảng quiz_history nếu chưa có
    # ============================================================
    if "quiz_history" not in tables:
        print("[MIGRATE] Tạo bảng quiz_history...")
        cursor.execute("""
            CREATE TABLE quiz_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id),
                session_id VARCHAR(100) NOT NULL,
                doc_id INTEGER NOT NULL,
                chunk_id VARCHAR(100) NOT NULL,
                is_correct INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        print("[OK] Tạo bảng quiz_history xong.")
    else:
        cols = get_existing_columns(conn, "quiz_history")
        if "user_id" not in cols:
            cursor.execute("ALTER TABLE quiz_history ADD COLUMN user_id INTEGER REFERENCES users(id)")
            conn.commit()
        print("[SKIP] Bảng quiz_history đã tồn tại.")

    # ============================================================
    # 5. Tạo bảng user_knowledge nếu chưa có
    # ============================================================
    if "user_knowledge" not in tables:
        print("[MIGRATE] Tạo bảng user_knowledge...")
        cursor.execute("""
            CREATE TABLE user_knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id),
                session_id VARCHAR(100) NOT NULL,
                doc_id INTEGER NOT NULL,
                chunk_id VARCHAR(100) NOT NULL,
                probability INTEGER DEFAULT 50,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        print("[OK] Tạo bảng user_knowledge xong.")
    else:
        cols = get_existing_columns(conn, "user_knowledge")
        if "user_id" not in cols:
            cursor.execute("ALTER TABLE user_knowledge ADD COLUMN user_id INTEGER REFERENCES users(id)")
            conn.commit()
        print("[SKIP] Bảng user_knowledge đã tồn tại.")

    # ============================================================
    # Kết quả cuối
    # ============================================================
    tables_after = get_existing_tables(conn)
    print(f"\n[DONE] Migration hoàn tất. Bảng hiện có: {tables_after}")
    
    for table in tables_after:
        cols = get_existing_columns(conn, table)
        print(f"  {table}: {cols}")

    conn.close()

if __name__ == "__main__":
    migrate()
