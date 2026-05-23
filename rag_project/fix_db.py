"""
Fix migration: them cac cot con thieu vao backend/rag.db
"""
import sqlite3

db_path = "backend/rag.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# === documents table ===
cursor.execute("PRAGMA table_info(documents)")
cols = {c[1] for c in cursor.fetchall()}
print("documents columns:", cols)

if "user_id" not in cols:
    print("Adding user_id to documents...")
    cursor.execute("ALTER TABLE documents ADD COLUMN user_id INTEGER")
    conn.commit()
    print("OK")
else:
    print("user_id already exists in documents")

# === chat_history table ===
cursor.execute("PRAGMA table_info(chat_history)")
chat_cols = {c[1] for c in cursor.fetchall()}
print("chat_history columns:", chat_cols)

if "user_id" not in chat_cols:
    print("Adding user_id to chat_history...")
    cursor.execute("ALTER TABLE chat_history ADD COLUMN user_id INTEGER")
    conn.commit()
    print("OK")
else:
    print("user_id already exists in chat_history")

# === users table ===
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
if not cursor.fetchone():
    print("Creating users table...")
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
    print("users table created")
else:
    print("users table already exists")

# === quiz_history table ===
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quiz_history'")
if not cursor.fetchone():
    print("Creating quiz_history table...")
    cursor.execute("""
        CREATE TABLE quiz_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_id VARCHAR(100) NOT NULL,
            doc_id INTEGER NOT NULL,
            chunk_id VARCHAR(100) NOT NULL,
            is_correct INTEGER NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    print("quiz_history created")
else:
    cursor.execute("PRAGMA table_info(quiz_history)")
    qh_cols = {c[1] for c in cursor.fetchall()}
    if "user_id" not in qh_cols:
        cursor.execute("ALTER TABLE quiz_history ADD COLUMN user_id INTEGER")
        conn.commit()
        print("Added user_id to quiz_history")

# === user_knowledge table ===
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_knowledge'")
if not cursor.fetchone():
    print("Creating user_knowledge table...")
    cursor.execute("""
        CREATE TABLE user_knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_id VARCHAR(100) NOT NULL,
            doc_id INTEGER NOT NULL,
            chunk_id VARCHAR(100) NOT NULL,
            probability INTEGER DEFAULT 50,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    print("user_knowledge created")
else:
    cursor.execute("PRAGMA table_info(user_knowledge)")
    uk_cols = {c[1] for c in cursor.fetchall()}
    if "user_id" not in uk_cols:
        cursor.execute("ALTER TABLE user_knowledge ADD COLUMN user_id INTEGER")
        conn.commit()
        print("Added user_id to user_knowledge")

conn.close()
print("\nMigration completed successfully!")
