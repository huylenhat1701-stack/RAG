"""
Document Service - Xử lý upload, chunking và indexing tài liệu.
Hỗ trợ: PDF (PyMuPDF), DOCX (python-docx), TXT, MD
"""

import shutil
from pathlib import Path
from typing import Tuple, Optional

from ..core.config import UPLOAD_DIR, BASE_DIR
from ..repositories.document_repo import DocumentRepository
from ..services.llm_service import LLMService

def get_safe_file_path(db_path: str) -> Path:
    """
    Giải quyết đường dẫn file tài liệu an toàn.
    Kiểm tra nếu đường dẫn lưu trong DB là tuyệt đối và tồn tại,
    ngược lại giải quyết tương đối theo BASE_DIR hoặc UPLOAD_DIR.
    """
    path = Path(db_path)
    if path.is_absolute() and path.exists():
        return path
    
    # Thử tương đối với BASE_DIR (nếu path dạng 'uploads/filename')
    resolved_path = BASE_DIR / path
    if resolved_path.exists():
        return resolved_path
        
    # Thử trực tiếp trong UPLOAD_DIR (chỉ lấy filename)
    resolved_path = UPLOAD_DIR / path.name
    if resolved_path.exists():
        return resolved_path
        
    # Fallback về UPLOAD_DIR/filename
    return UPLOAD_DIR / path.name



def _extract_text_from_pdf(file_path: Path) -> Tuple[str, int]:
    """
    Bóc tách text từ file PDF sử dụng PyMuPDF.
    Returns: (text, page_count)
    """
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(file_path))
        texts = []
        for page in doc:
            texts.append(page.get_text())
        page_count = len(doc)
        doc.close()
        return "\n".join(texts), page_count
    except ImportError:
        raise ImportError("PyMuPDF chưa được cài. Chạy: pip install pymupdf")
    except Exception as e:
        raise RuntimeError(f"Lỗi đọc PDF: {e}")


def _extract_text_from_docx(file_path: Path) -> Tuple[str, int]:
    """
    Bóc tách text từ file DOCX sử dụng python-docx.
    Returns: (text, page_count_estimate)
    """
    try:
        from docx import Document
        doc = Document(str(file_path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n".join(paragraphs)
        # Ước tính số trang: ~300 từ/trang
        word_count = len(text.split())
        page_estimate = max(1, word_count // 300)
        return text, page_estimate
    except ImportError:
        raise ImportError("python-docx chưa được cài. Chạy: pip install python-docx")
    except Exception as e:
        raise RuntimeError(f"Lỗi đọc DOCX: {e}")


def _extract_text_from_txt(file_path: Path) -> Tuple[str, int]:
    """
    Đọc text từ file TXT/MD.
    Returns: (text, page_count_estimate)
    """
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = file_path.read_text(encoding="latin-1")
    word_count = len(text.split())
    page_estimate = max(1, word_count // 300)
    return text, page_estimate


def _create_temp_txt(file_path: Path, text: str) -> Path:
    """Tạo file TXT tạm để LocalRAG có thể đọc."""
    txt_path = file_path.with_suffix(".extracted.txt")
    txt_path.write_text(text, encoding="utf-8")
    return txt_path


def extract_document_text(file_path: Path, file_type: str) -> Tuple[str, int]:
    """
    Bóc tách text từ tài liệu theo loại file và làm sạch các ký tự đặc biệt gây lỗi.
    
    Returns:
        Tuple (text, page_count)
    """
    if file_type == "pdf":
        text, page_count = _extract_text_from_pdf(file_path)
    elif file_type == "docx":
        text, page_count = _extract_text_from_docx(file_path)
    elif file_type in ("txt", "md"):
        text, page_count = _extract_text_from_txt(file_path)
    else:
        # Thử đọc như text
        text, page_count = _extract_text_from_txt(file_path)

    # LÀM SẠCH VĂN BẢN (Sanitize Text)
    # Loại bỏ NULL bytes (\x00) gây lỗi "A string literal cannot contain NUL" trong SQLite và Chroma
    if text:
        text = text.replace('\x00', '')
        text = text.replace('\u0000', '')

    return text, page_count


def get_document_content(doc_id: int, doc_repo: DocumentRepository) -> Optional[dict]:
    """
    Đọc và trả về nội dung đầy đủ của tài liệu.
    
    Returns:
        dict với keys: content, word_count, char_count, page_count
        hoặc None nếu không tìm thấy
    """
    doc = doc_repo.get_by_id(doc_id)
    if not doc:
        return None

    file_path = get_safe_file_path(doc.file_path)
    file_type = doc.file_type or ""

    # Ưu tiên file extracted.txt nếu có
    extracted_path = file_path.with_suffix(".extracted.txt")
    if extracted_path.exists():
        try:
            content = extracted_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = extracted_path.read_text(encoding="latin-1")
        word_count = len(content.split())
        return {
            "content": content,
            "word_count": word_count,
            "char_count": len(content),
            "page_count": doc.page_count or max(1, word_count // 300),
        }

    # Đọc từ file gốc
    if not file_path.exists():
        return None

    try:
        text, page_count = extract_document_text(file_path, file_type)
        word_count = len(text.split())
        return {
            "content": text,
            "word_count": word_count,
            "char_count": len(text),
            "page_count": page_count,
        }
    except Exception as e:
        return {"content": f"Lỗi đọc tài liệu: {e}", "word_count": 0, "char_count": 0, "page_count": 0}


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
        3. Lưu content_preview + page_count
        4. LocalRAG.load_files() → chunk
        5. LocalRAG.index_knowledge_base() → embed & lưu ChromaDB
        6. Cập nhật trạng thái → INDEXED + chunk_count

    Returns:
        Số chunk đã index
    """
    # Bước 1: Đánh dấu đang xử lý
    doc_repo.update_status(doc_id, "INDEXING")

    try:
        # Bước 2: Bóc tách text tuỳ loại file
        text, page_count = extract_document_text(file_path, file_type)
        
        # Bước 2.5: Lưu preview và page count
        preview = text[:500].strip() if text else ""
        doc_repo.update_content_preview(doc_id, preview, page_count)

        # Bước 3: Tạo file tạm nếu cần
        if file_type in ("pdf", "docx"):
            path_to_load = _create_temp_txt(file_path, text)
        else:
            path_to_load = file_path

        # Bước 4 & 5: Load vào LocalRAG và Index
        chunk_count = llm_service.load_files_into_kb([str(path_to_load)], original_filenames=[file_path.name])

        # Bước 6: Cập nhật DB
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
    Khởi động lại server → nạp lại tất cả tài liệu đã INDEXED vào RAM.
    Cần thiết vì LocalRAG lưu KB trong memory.

    Ưu tiên dùng file .extracted.txt vì LocalRAG không parse được binary PDF/DOCX.
    """
    indexed_docs = doc_repo.get_indexed()
    if not indexed_docs:
        print("ℹ️ Không có tài liệu đã index nào để reload.")
        return

    file_paths = []
    for doc in indexed_docs:
        p = get_safe_file_path(doc.file_path)

        # Ưu tiên 1: file .extracted.txt (LocalRAG đọc được tốt nhất)
        txt_p = p.with_suffix(".extracted.txt")
        if txt_p.exists():
            file_paths.append(str(txt_p))
            continue

        # Ưu tiên 2: file gốc (chỉ phù hợp với TXT/MD, không phù hợp PDF/DOCX)
        if p.exists():
            file_paths.append(str(p))
        else:
            print(f"⚠️  Không tìm thấy file cho doc ID={doc.id}: {p}")

    if file_paths:
        count = llm_service.reload_all_files(file_paths)
        print(f"[OK] Reload thanh cong {count} chunks tu {len(file_paths)} file.")

