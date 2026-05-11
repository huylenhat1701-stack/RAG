"""
RAG Service - Điều phối luồng Hỏi & Đáp và Tóm tắt tài liệu
Full-Context Edition: tự động chọn chế độ đọc toàn bộ hoặc RAG tùy độ dài tài liệu.
"""

from pathlib import Path
from typing import List
from sqlalchemy.orm import Session

from ..repositories.document_repo import DocumentRepository
from ..repositories.history_repo import HistoryRepository
from ..services.llm_service import LLMService, SearchResult
from ..services.document_service import get_document_content
from ..models.schemas import AskResponse, SourceInfo, DocumentSummaryResponse, ExerciseResponse, QuizResponse, QuizQuestion
from ..core.config import (
    SUMMARY_SYSTEM_PROMPT,
    LLM_MAX_CONTENT_CHARS,
    FULL_CONTEXT_THRESHOLD_CHARS,
)


def answer_question(
    question: str,
    top_k: int,
    db: Session,
    llm_service: LLMService,
    history: List[dict] = None,
    doc_ids: List[int] = None,
) -> AskResponse:
    """
    Luồng Q&A với Full-Context Mode:

    TRƯỜNG HỢP 1: Người dùng chọn 1 tài liệu cụ thể
        → Đọc toàn bộ nội dung tài liệu đó
        → Nếu vừa context window: Full-Context Mode (chính xác 100%)
        → Nếu quá lớn: RAG Mode với max top_k (vẫn rất tốt)

    TRƯỜNG HỢP 2: Người dùng chọn nhiều tài liệu hoặc tất cả
        → Ghép toàn bộ nội dung các tài liệu đã chọn
        → Nếu vừa: Full-Context Mode ghép nhiều tài liệu
        → Nếu quá lớn: RAG Mode với top_k cao
    """
    doc_repo = DocumentRepository(db)
    hist_repo = HistoryRepository(db)

    indexed_count = doc_repo.count_indexed()
    if indexed_count == 0:
        return AskResponse(
            question=question,
            answer=(
                "Chưa có tài liệu nào được tải lên và xử lý.\n"
                "Vui lòng vào tab Quản Lý Tài Liệu để upload tài liệu trước."
            ),
            sources=[],
            model_used=llm_service._model_name,
            history_id=-1,
            mode="none",
            context_chars=0,
        )

    # ----------------------------------------------------------------
    # Xây dựng danh sách tài liệu được phép truy cập
    # ----------------------------------------------------------------
    allowed_filenames = None
    target_docs = []  # Danh sách doc objects để đọc full content

    if doc_ids:
        allowed_filenames = []
        for did in doc_ids:
            doc = doc_repo.get_by_id(did)
            if doc:
                allowed_filenames.append(Path(doc.file_path).name)
                target_docs.append(doc)
    else:
        # Không chọn cụ thể → lấy tất cả tài liệu đã INDEXED
        target_docs = doc_repo.get_indexed()

    # ----------------------------------------------------------------
    # Thử Full-Context Mode: đọc toàn bộ nội dung tài liệu
    # ----------------------------------------------------------------
    combined_content = ""
    doc_labels = []

    for doc in target_docs:
        content_data = get_document_content(doc.id, doc_repo)
        if content_data and content_data.get("content"):
            content = content_data["content"]
            doc_labels.append(doc.file_name)

            if len(target_docs) == 1:
                # 1 tài liệu: không cần header phân cách
                combined_content = content
            else:
                # Nhiều tài liệu: thêm header phân cách
                combined_content += (
                    f"\n\n{'='*60}\n"
                    f"TÀI LIỆU: {doc.file_name}\n"
                    f"{'='*60}\n"
                    f"{content}"
                )

    # Quyết định chế độ dựa trên tổng độ dài nội dung
    use_full_context = (
        combined_content
        and len(combined_content) <= FULL_CONTEXT_THRESHOLD_CHARS
    )

    # ----------------------------------------------------------------
    # FULL-CONTEXT MODE: Đưa toàn bộ nội dung vào LLM
    # ----------------------------------------------------------------
    if use_full_context:
        mode = "full_context"
        context_chars = len(combined_content)
        filename_label = ", ".join(doc_labels) if doc_labels else ""

        print(f"[Full-Context Mode] {len(doc_labels)} tài liệu, {context_chars:,} ký tự")

        try:
            answer = llm_service.generate_answer_full_context(
                question=question,
                full_text=combined_content,
                filename=filename_label,
                history=history,
            )
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Lỗi sinh câu trả lời (Full-Context): {str(e)}")

        # Nguồn trích dẫn = các tài liệu đã đọc
        sources_for_response = [
            SourceInfo(file_name=name, relevance_score=1.0)
            for name in doc_labels
        ]
        sources_for_db = doc_labels

    # ----------------------------------------------------------------
    # RAG MODE: Tài liệu quá lớn → dùng vector search + top_k lớn
    # ----------------------------------------------------------------
    else:
        mode = "rag"
        print(f"[RAG Mode] Nội dung quá lớn ({len(combined_content):,} ký tự), dùng vector search top_k={top_k}")

        try:
            search_results: List[SearchResult] = llm_service.search(
                question, top_k=top_k, allowed_filenames=allowed_filenames
            )
        except Exception as e:
            raise RuntimeError(f"Lỗi tìm kiếm: {str(e)}")

        context_chars = sum(len(r.chunk.text) for r in search_results)

        try:
            answer = llm_service.generate_answer(
                question=question,
                context_chunks=search_results,
                history=history,
            )
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Lỗi sinh câu trả lời (RAG): {str(e)}")

        # Build sources
        sources_for_response = []
        sources_for_db = []
        seen = set()
        for r in search_results:
            fn = r.chunk.filename
            if fn not in seen:
                seen.add(fn)
                sources_for_response.append(SourceInfo(file_name=fn, relevance_score=round(r.score, 3)))
                sources_for_db.append(fn)

    # ----------------------------------------------------------------
    # Lưu lịch sử
    # ----------------------------------------------------------------
    hist = hist_repo.create(
        question=question,
        answer=answer,
        sources=sources_for_db,
        model_used=llm_service._model_name,
    )

    return AskResponse(
        question=question,
        answer=answer,
        sources=sources_for_response,
        model_used=llm_service._model_name,
        history_id=hist.id,
        mode=mode,
        context_chars=context_chars,
    )


def summarize_document(
    doc_id: int,
    db: Session,
    llm_service: LLMService,
) -> DocumentSummaryResponse:
    """
    Tóm tắt tài liệu — Full-Context khi có thể, phân đoạn khi tài liệu lớn.
    Không giới hạn độ dài nội dung.
    """
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(doc_id)
    if not doc:
        raise ValueError(f"Không tìm thấy tài liệu ID={doc_id}")

    # Nếu đã có summary → trả luôn
    if doc.summary:
        return DocumentSummaryResponse(
            id=doc.id,
            file_name=doc.file_name,
            summary=doc.summary,
            model_used=llm_service._model_name,
        )

    content_data = get_document_content(doc_id, doc_repo)
    if not content_data or not content_data["content"]:
        raise ValueError("Không thể đọc nội dung tài liệu")

    content = content_data["content"]
    max_chars = LLM_MAX_CONTENT_CHARS  # Dùng giới hạn đã tăng rất cao

    # Nếu nội dung vừa → tóm tắt thẳng toàn bộ
    if len(content) <= max_chars:
        prompt = f"TÀI LIỆU: {doc.file_name}\n\nNỘI DUNG:\n{content}"
        summary = llm_service.chat_direct(prompt=prompt, system_prompt=SUMMARY_SYSTEM_PROMPT)
    else:
        # Chia thành các phần và tóm tắt từng phần (tài liệu rất lớn)
        segment_size = max_chars // 2  # Mỗi phần nhỏ hơn để có room cho prompt
        segments = [content[i:i + segment_size] for i in range(0, len(content), segment_size)]

        print(f"[Summarize] Tài liệu dài ({len(content):,} ký tự), chia {len(segments)} đoạn...")

        part_summaries = []
        for idx, part in enumerate(segments, 1):
            part_label = f"[Phần {idx}/{len(segments)}] "
            prompt = f"{part_label}TÀI LIỆU: {doc.file_name}\n\nNỘI DUNG:\n{part}"
            partial = llm_service.chat_direct(prompt=prompt, system_prompt=SUMMARY_SYSTEM_PROMPT)
            part_summaries.append(f"**Phần {idx}:**\n{partial}")

        # Tóm tắt tổng hợp từ các tóm tắt con
        combined = "\n\n".join(part_summaries)
        if len(combined) > max_chars:
            combined = combined[:max_chars]

        final_prompt = (
            f"Dưới đây là tóm tắt từng phần của tài liệu '{doc.file_name}'.\n"
            f"Hãy tổng hợp thành 1 bản tóm tắt hoàn chỉnh, mạch lạc:\n\n{combined}"
        )
        summary = llm_service.chat_direct(
            prompt=final_prompt,
            system_prompt="Tổng hợp và tóm tắt lại bằng tiếng Việt, đầy đủ, có bullet points."
        )

    doc_repo.update_summary(doc_id, summary)

    return DocumentSummaryResponse(
        id=doc.id,
        file_name=doc.file_name,
        summary=summary,
        model_used=llm_service._model_name,
    )


def generate_exercise(
    doc_id: int,
    exercise_type: str,
    count: int,
    db: Session,
    llm_service: LLMService,
) -> ExerciseResponse:
    """Tạo bài tập từ nội dung đầy đủ của tài liệu."""
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(doc_id)
    if not doc:
        raise ValueError(f"Không tìm thấy tài liệu ID={doc_id}")

    content_data = get_document_content(doc_id, doc_repo)
    if not content_data or not content_data["content"]:
        raise ValueError("Không thể đọc nội dung tài liệu")

    # Đọc tối đa nội dung có thể (không cắt cứng)
    content = llm_service._safe_truncate(content_data["content"], LLM_MAX_CONTENT_CHARS)

    prompt = (
        f"TẠO {exercise_type.upper()} TỪ TÀI LIỆU: {doc.file_name}\n\n"
        f"YÊU CẦU: Tạo {count} câu {exercise_type} rõ ràng, có đáp án chi tiết.\n"
        f"Câu hỏi phải bám sát nội dung tài liệu.\n\n"
        f"NỘI DUNG TÀI LIỆU:\n{content}"
    )

    exercise_text = llm_service.chat_direct(
        prompt=prompt,
        system_prompt=f"Bạn là trợ lý giáo dục. Tạo {exercise_type} từ tài liệu bằng tiếng Việt, câu hỏi rõ ràng và có đáp án."
    )

    return ExerciseResponse(
        id=doc.id,
        file_name=doc.file_name,
        exercise_text=exercise_text,
        model_used=llm_service._model_name,
    )


def generate_quiz(
    doc_id: int,
    count: int,
    db: Session,
    llm_service: LLMService,
) -> QuizResponse:
    """
    Tạo bộ câu hỏi thi trắc nghiệm.
    Chiến lược: tạo từng batch nhỏ 3 câu/lần để model nhỏ dễ tuân thủ JSON.
    """
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(doc_id)
    if not doc:
        raise ValueError(f"Không tìm thấy tài liệu ID={doc_id}")

    content_data = get_document_content(doc_id, doc_repo)
    if not content_data or not content_data["content"]:
        raise ValueError("Không thể đọc nội dung tài liệu")

    # Giới hạn content để model nhỏ không bị overwhelm
    content = llm_service._safe_truncate(content_data["content"], min(LLM_MAX_CONTENT_CHARS, 3000))

    all_questions: list = []
    batch_size = 3  # Tạo 3 câu/lần — model nhỏ dễ làm hơn
    q_index = 1

    for batch_start in range(0, count, batch_size):
        batch_count = min(batch_size, count - batch_start)
        batch_qs = _generate_quiz_batch(
            llm_service=llm_service,
            content=content,
            filename=doc.file_name,
            batch_count=batch_count,
            start_index=q_index,
        )
        all_questions.extend(batch_qs)
        q_index += len(batch_qs)
        if len(all_questions) >= count:
            break

    # Re-index
    for i, q in enumerate(all_questions):
        q.id = i + 1

    return QuizResponse(
        id=doc.id,
        file_name=doc.file_name,
        questions=all_questions[:count],
        total=len(all_questions[:count]),
        model_used=llm_service._model_name,
    )


def _generate_quiz_batch(
    llm_service,
    content: str,
    filename: str,
    batch_count: int,
    start_index: int,
) -> list:
    """Tạo một batch nhỏ câu hỏi. Thử JSON trước, fallback parse text thô."""

    # ── Prompt đơn giản nhất có thể cho model nhỏ ──────────
    prompt = f"""Đọc đoạn văn sau và tạo {batch_count} câu hỏi trắc nghiệm (A/B/C/D).

VĂN BẢN:
{content[:2500]}

Viết kết quả theo mẫu sau, KHÔNG thêm gì khác:

Câu 1: [nội dung câu hỏi]
A. [lựa chọn A]
B. [lựa chọn B]
C. [lựa chọn C]
D. [lựa chọn D]
Đáp án: A
Giải thích: [giải thích ngắn]

Câu 2: [nội dung câu hỏi]
A. [lựa chọn A]
B. [lựa chọn B]
C. [lựa chọn C]
D. [lựa chọn D]
Đáp án: B
Giải thích: [giải thích ngắn]"""

    raw = llm_service.chat_direct(
        prompt=prompt,
        system_prompt="Bạn là giáo viên. Tạo câu hỏi trắc nghiệm bằng tiếng Việt theo đúng mẫu được yêu cầu."
    )

    print(f"[Quiz] Raw response (first 400 chars): {raw[:400]}")

    # Làm sạch preamble của AI trước khi parse
    raw = _clean_ai_preamble(raw)

    # Thử JSON trước
    json_result = _try_parse_json(raw)
    if json_result:
        return [_normalize_question(q, start_index + i) for i, q in enumerate(json_result)]

    # Fallback: parse text thô theo mẫu "Câu N: ..."
    return _parse_text_format(raw, start_index)


def _clean_ai_preamble(raw: str) -> str:
    """
    Xóa bỏ những dòng 'rác' mà model nhỏ thường thêm vào trước câu hỏi:
    - Lời cảm ơn / xác nhận: "Tuyệt vời!", "Chắc chắn rồi!", "Dưới đây là..."
    - Markdown bold: **text**
    - Câu giới thiệu trước block câu hỏi đầu tiên
    """
    import re

    lines = raw.splitlines()
    result_lines = []
    found_first_question = False

    # Pattern nhận biết dòng bắt đầu một câu hỏi
    question_start = re.compile(
        r'^(?:Câu\s*\d+[:\.]|\*\*Câu\s*\d+\*\*|Question\s*\d+[:\.]|\d+[\.)\:])',
        re.IGNORECASE
    )

    for line in lines:
        if question_start.match(line.strip()):
            found_first_question = True
        if found_first_question:
            # Xóa markdown bold/italic trong mọi dòng
            clean = re.sub(r'\*\*(.+?)\*\*', r'\1', line)
            clean = re.sub(r'\*(.+?)\*', r'\1', clean)
            clean = re.sub(r'__(.+?)__', r'\1', clean)
            result_lines.append(clean)

    # Nếu không tìm thấy cấu trúc "Câu N:" → giữ nguyên (dể fallback parse)
    if not result_lines:
        # Vẫn xóa markdown
        cleaned = re.sub(r'\*\*(.+?)\*\*', r'\1', raw)
        cleaned = re.sub(r'\*(.+?)\*', r'\1', cleaned)
        return cleaned

    return '\n'.join(result_lines)


def _clean_question_text(text: str) -> str:
    """
    Làm sạch text câu hỏi:
    - Xóa prefix 'Câu N:' nếu sót lại trong nội dung
    - Xóa markdown bold/italic
    - Strip khoảng trắng thừa
    """
    import re
    text = re.sub(r'^(?:Câu\s*\d+[:\.\s]+|Question\s*\d+[:\.\s]+)', '', text.strip(), flags=re.IGNORECASE)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    return text.strip()


def _try_parse_json(raw: str) -> list:
    """Thử parse JSON từ response. Trả None nếu thất bại."""
    import json, re

    raw = raw.strip()

    # Thử parse thẳng
    try:
        data = json.loads(raw)
        if isinstance(data, list) and data:
            return data
    except Exception:
        pass

    # Tìm JSON array trong text
    for pattern in [
        r'\[\s*\{.*?\}\s*\]',
        r'```(?:json)?\s*(\[.*?\])\s*```',
    ]:
        match = re.search(pattern, raw, re.DOTALL)
        if match:
            try:
                s = match.group(1) if match.lastindex else match.group()
                data = json.loads(s)
                if isinstance(data, list) and data:
                    return data
            except Exception:
                pass

    return None


def _parse_text_format(raw: str, start_index: int) -> list:
    """
    Parse định dạng text thô mà model nhỏ hay trả về:
    Câu 1: ...
    A. ...
    B. ...
    Đáp án: A
    Giải thích: ...
    """
    import re

    questions = []
    # Tách theo "Câu N:" hoặc "**Câu N**" hoặc "Question N:"
    blocks = re.split(
        r'\n(?:Câu\s+\d+[:\.]|Question\s+\d+[:\.]|\*\*Câu\s+\d+\*\*[:\.]|\d+[\.\)])',
        raw, flags=re.IGNORECASE
    )

    for i, block in enumerate(blocks):
        block = block.strip()
        if not block:
            continue

        q_text = ""
        opts = {"A": "", "B": "", "C": "", "D": ""}
        answer = "A"
        expl = ""

        lines = [l.strip() for l in block.split('\n') if l.strip()]
        collecting_q = True

        for line in lines:
            # Lựa chọn A/B/C/D
            opt_match = re.match(r'^([ABCD])[.\)]\s*(.+)', line, re.IGNORECASE)
            if opt_match:
                key = opt_match.group(1).upper()
                # Xóa markdown khỏi lựa chọn
                opt_text = re.sub(r'\*\*(.+?)\*\*', r'\1', opt_match.group(2).strip())
                opt_text = re.sub(r'\*(.+?)\*', r'\1', opt_text).strip()
                opts[key] = opt_text
                collecting_q = False
                continue

            # Đáp án
            ans_match = re.match(r'^(?:Đáp án|Answer|Correct)[:\s]+([ABCD])', line, re.IGNORECASE)
            if ans_match:
                answer = ans_match.group(1).upper()
                collecting_q = False
                continue

            # Giải thích
            expl_match = re.match(r'^(?:Giải thích|Explanation)[:\s]+(.+)', line, re.IGNORECASE)
            if expl_match:
                expl = expl_match.group(1).strip()
                collecting_q = False
                continue

            # Dòng đầu là câu hỏi
            if collecting_q:
                q_text += (" " if q_text else "") + line

        # Chỉ thêm nếu có câu hỏi + ít nhất 2 lựa chọn
        filled = sum(1 for v in opts.values() if v)
        if q_text and filled >= 2:
            for key in ["A", "B", "C", "D"]:
                if not opts[key]:
                    opts[key] = "(Không có)"
            questions.append(QuizQuestion(
                id=start_index + len(questions),
                question=_clean_question_text(q_text),
                options=opts,
                answer=answer if answer in opts else "A",
                explanation=expl,
            ))

    # Nếu không parse được gì — thử split theo số thứ tự đơn giản hơn
    if not questions:
        questions = _parse_numbered_fallback(raw, start_index)

    return questions


def _parse_numbered_fallback(raw: str, start_index: int) -> list:
    """Fallback cuối: tìm bất kỳ cấu trúc hỏi-đáp nào trong text."""
    import re

    questions = []
    # Tìm các dòng chứa A. B. C. D. liên tiếp
    lines = raw.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Tìm câu hỏi (dòng kết thúc bằng ?)
        if '?' in line and len(line) > 10:
            q_text = line
            opts = {"A": "", "B": "", "C": "", "D": ""}
            answer = "A"
            expl = ""
            j = i + 1
            while j < min(i + 10, len(lines)):
                l = lines[j].strip()
                m = re.match(r'^([ABCD])[.\)]\s*(.+)', l, re.IGNORECASE)
                if m:
                    opts[m.group(1).upper()] = m.group(2)
                am = re.match(r'^(?:Đáp án|Answer)[:\s]+([ABCD])', l, re.IGNORECASE)
                if am:
                    answer = am.group(1).upper()
                em = re.match(r'^(?:Giải thích|Explanation)[:\s]+(.+)', l, re.IGNORECASE)
                if em:
                    expl = em.group(1)
                j += 1

            filled = sum(1 for v in opts.values() if v)
            if filled >= 2:
                for key in ["A", "B", "C", "D"]:
                    if not opts[key]:
                        opts[key] = "(Không có)"
                questions.append(QuizQuestion(
                    id=start_index + len(questions),
                    question=q_text,
                    options=opts,
                    answer=answer,
                    explanation=expl,
                ))
            i = j
        else:
            i += 1

    return questions


def _normalize_question(q: dict, idx: int) -> QuizQuestion:
    """Chuẩn hóa một câu hỏi từ dict về QuizQuestion."""
    options = q.get("options", {})
    if not isinstance(options, dict):
        options = {"A": "?", "B": "?", "C": "?", "D": "?"}
    for key in ["A", "B", "C", "D"]:
        if key not in options:
            options[key] = "(Không có)"

    answer = str(q.get("answer", "A")).strip().upper()
    if answer not in ["A", "B", "C", "D"]:
        answer = "A"

    return QuizQuestion(
        id=idx,
        question=str(q.get("question", f"Câu hỏi {idx}")),
        options=options,
        answer=answer,
        explanation=str(q.get("explanation", "")),
    )

