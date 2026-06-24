import sqlite3
from pathlib import Path

def migrate():
    # File db đặt tại rag_project/backend/rag.db
    db_path = Path(__file__).parent.parent / "rag.db"
    print(f"[Migration] Database path: {db_path.absolute()}")
    
    if not db_path.exists():
        print("[Migration] Database file does not exist. Skipping.")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Lấy thông tin các cột trong bảng quiz_history
    cursor.execute("PRAGMA table_info(quiz_history)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if "bloom_level" not in columns:
        print("[Migration] Adding 'bloom_level' column to 'quiz_history' table...")
        cursor.execute("ALTER TABLE quiz_history ADD COLUMN bloom_level VARCHAR(20) DEFAULT NULL")
        conn.commit()
        print("[Migration] Column 'bloom_level' added successfully.")
    else:
        print("[Migration] Column 'bloom_level' already exists in 'quiz_history'.")
        
    conn.close()

if __name__ == "__main__":
    migrate()
