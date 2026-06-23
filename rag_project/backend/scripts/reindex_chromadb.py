"""
Script re-index toàn bộ ChromaDB.
Xóa collection cũ và rebuild từ các file đã upload.

Dùng khi:
- Thêm metadata field mới vào indexing (ví dụ: file_stem)
- ChromaDB bị corrupted

Chạy: python scripts/reindex_chromadb.py
"""
import sys
from pathlib import Path

# Thêm project root vào path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.config import CHROMA_PERSIST_DIR, DATABASE_URL
from backend.db.database import SessionLocal
from backend.repositories.document_repo import DocumentRepository
from backend.services.document_service import process_and_index_document

import chromadb


def reindex_all():
    """Xóa ChromaDB collection và rebuild từ DB records."""
    print("=" * 60)
    print("RE-INDEX ChromaDB — Full Rebuild")
    print("=" * 60)

    # Xóa collection cũ
    client = chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))
    KB_NAME = "rag_knowledge_base"
    try:
        client.delete_collection(name=KB_NAME)
        print(f"[OK] Đã xóa collection '{KB_NAME}' cũ.")
    except Exception as e:
        print(f"[INFO] Collection '{KB_NAME}' không tồn tại hoặc lỗi xóa: {e}")

    # Khởi tạo service (tạo lại collection trống)
    print("[INFO] Khởi tạo LLMService...")
    from backend.services.llm_service import LLMService
    llm_service = LLMService()

    # Lấy tất cả tài liệu đã indexed từ DB
    db = SessionLocal()
    try:
        doc_repo = DocumentRepository(db)
        docs = doc_repo.get_all()
        indexed_docs = [d for d in docs if d.status.upper() == "INDEXED"]
        print(f"[INFO] Tìm thấy {len(indexed_docs)} tài liệu đã indexed trong DB.")

        success = 0
        failed = 0
        for doc in indexed_docs:
            file_path = Path(doc.file_path)
            # Thử file extracted trước
            extracted_path = file_path.with_suffix(".extracted.txt")
            if extracted_path.exists():
                target_path = extracted_path
            elif file_path.exists():
                target_path = file_path
            else:
                print(f"[WARN] File không tồn tại: {doc.file_name} ({file_path})")
                failed += 1
                continue

            try:
                count = llm_service.load_files_into_kb([str(target_path)])
                print(f"[OK] Re-indexed: {doc.file_name} → {count} chunks tổng cộng")
                success += 1
            except Exception as e:
                print(f"[ERROR] Lỗi index {doc.file_name}: {e}")
                failed += 1

        print()
        print("=" * 60)
        print(f"Re-index hoàn tất: {success} thành công, {failed} lỗi")
        print(f"Tổng chunks trong ChromaDB: {llm_service._collection.count()}")
        print("=" * 60)
    finally:
        db.close()


if __name__ == "__main__":
    reindex_all()
