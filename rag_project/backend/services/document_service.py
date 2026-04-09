"""
Document Service - Xử lý upload, chunking và indexing tài liệu.
Hỗ trợ: PDF (PyMuPDF), DOCX (python-docx), TXT
"""

import shutil
from pathlib import Path
from typing import Tuple

from ..core.config import UPLOAD_DIR
from ..repositories.document_repo import DocumentRepository
from ..services.llm_service import LLMService


def _extract_text_from_pdf(file_path: Path) -> str:
    """Bóc tách text từ file PDF sử dụng PyMuPDF."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(file_path))
        texts = []
        for page in doc:
            texts.append(page.get_text())
        doc.close()
        return "\n".join(texts)
    except ImportError:
        raise ImportError("PyMuPDF chưa được cài. Chạy: pip install pymupdf")
    except Exception as e:
        raise RuntimeError(f"Lỗi đọc PDF: {e}")


def _extract_text_from_docx(file_path: Path) -> str:
    """Bóc tách text từ file DOCX sử dụng python-docx."""
    try:
        from docx import Document
        doc = Document(str(file_path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs)
    except ImportError:
        raise ImportError("python-docx chưa được cài. Chạy: pip install python-docx")
    except Exception as e:
        raise RuntimeError(f"Lỗi đọc DOCX: {e}")


def _create_temp_txt(file_path: Path, text: str) -> Path:
    """Tạo file TXT tạm để LocalRAG có thể đọc."""
    txt_path = file_path.with_suffix(".extracted.txt")
    txt_path.write_text(text, encoding="utf-8")
    return txt_path


def save_upload_file(upload_file_obj, filename: str) -> Tuple[Path, int]:
    """
    Lưu file upload vào thư mục UPLOAD_DIR.

    Args:
        upload_file_obj: SpooledTemporaryFile từ FastAPI
        filename: Tên file an toàn (đã sanitize)

    Returns:
        Tuple (đường dẫn file đã lưu, kích thước bytes)
    """
    dest_path = UPLOAD_DIR / filename
    # Nếu file trùng tên, thêm số
    counter = 1
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    while dest_path.exists():
        dest_path = UPLOAD_DIR / f"{stem}_{counter}{suffix}"
        counter += 1

    with open(dest_path, "wb") as f:
        shutil.copyfileobj(upload_file_obj, f)

    file_size = dest_path.stat().st_size
    return dest_path, file_size


def process_and_index_document(
    doc_id: int,
    file_path: Path,
    file_type: str,
    doc_repo: DocumentRepository,
    llm_service: LLMService,
) -> int:
    """
    Quy trình xử lý tài liệu và index vào ChromaDB.

    Luồng:
        1. Đổi trạng thái → INDEXING
        2. Bóc tách text (PDF/DOCX/TXT)
        3. LocalRAG.load_files() → chunk
        4. LocalRAG.index_knowledge_base() → embed & lưu ChromaDB
        5. Cập nhật trạng thái → INDEXED + chunk_count

    Returns:
        Số chunk đã index
    """
    # Bước 1: Đánh dấu đang xử lý
    doc_repo.update_status(doc_id, "INDEXING")

    try:
        # Bước 2: Bóc tách text tuỳ loại file
        path_to_load = file_path  # Mặc định dùng file gốc

        if file_type == "pdf":
            text = _extract_text_from_pdf(file_path)
            path_to_load = _create_temp_txt(file_path, text)
        elif file_type == "docx":
            text = _extract_text_from_docx(file_path)
            path_to_load = _create_temp_txt(file_path, text)
        elif file_type == "txt":
            path_to_load = file_path
        else:
            # Thử đọc như text file
            path_to_load = file_path

        # Bước 3 & 4: Load vào LocalRAG và Index
        chunk_count = llm_service.load_files_into_kb([str(path_to_load)])

        # Bước 5: Cập nhật DB
        doc_repo.update_status(doc_id, "INDEXED", chunk_count=chunk_count)
        print(f"✅ Document {doc_id} ({file_path.name}): INDEXED với {chunk_count} chunks")

        return chunk_count

    except Exception as e:
        error_msg = str(e)
        doc_repo.update_status(doc_id, "ERROR", error=error_msg)
        print(f"❌ Document {doc_id} lỗi: {error_msg}")
        raise


def reload_indexed_documents(doc_repo: DocumentRepository, llm_service: LLMService):
    """
    Khởi động lại server → nạp lại tất cả tài liệu đã INDEXED vào RAM/ChromaDB.
    Cần thiết vì LocalRAG lưu KB trong memory.
    """
    indexed_docs = doc_repo.get_indexed()
    if not indexed_docs:
        print("ℹ️ Không có tài liệu đã index nào để reload.")
        return

    file_paths = []
    for doc in indexed_docs:
        # Kiểm tra file còn tồn tại không
        p = Path(doc.file_path)
        if p.exists():
            file_paths.append(str(p))
        else:
            # Thử tìm file .extracted.txt
            txt_p = p.with_suffix(".extracted.txt")
            if txt_p.exists():
                file_paths.append(str(txt_p))

    if file_paths:
        count = llm_service.reload_all_files(file_paths)
        print(f"🔄 Reload thành công {count} chunks từ {len(file_paths)} file.")
