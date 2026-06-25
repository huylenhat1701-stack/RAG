"""
RAG Service - Điều phối luồng Hỏi & Đáp và Tóm tắt tài liệu
Full-Context Edition: tự động chọn chế độ đọc toàn bộ hoặc RAG tùy độ dài tài liệu.
"""

import json
import re
import random
from pathlib import Path
from typing import List
from sqlalchemy.orm import Session

from ..repositories.document_repo import DocumentRepository
from ..repositories.history_repo import HistoryRepository
from ..services.llm_service import LLMService, SearchResult
from ..services.document_service import get_document_content
from ..models.schemas import AskResponse, SourceInfo, DocumentSummaryResponse, ExerciseResponse, QuizResponse, QuizQuestion, LearningPathItem, LearningPathResponse
from ..core.config import (
    SUMMARY_SYSTEM_PROMPT,
    LLM_MAX_CONTENT_CHARS,
    FULL_CONTEXT_THRESHOLD_CHARS,
    RELEVANCE_THRESHOLD,
    NO_CONTEXT_THRESHOLD,
)


def split_into_sentences(text: str) -> List[str]:
    """
    Tách câu thông minh tránh ngắt câu tại chữ số thập phân (ví dụ: 3.14) 
    hoặc viết tắt học thuật/danh xưng tiếng Anh & tiếng Việt (ví dụ: TS., GS., ThS., PGS., Dr., Mr., vs.)
    và các chữ cái viết tắt tên riêng (ví dụ: N.V. An).
    """
    if not text:
        return []
        
    temp_text = text
    
    # 1. Bảo vệ các số thập phân (e.g. 3.14, 1.5)
    temp_text = re.sub(r'(\d+)\.(\d+)', r'\1_DECIMAL_DOT_\2', temp_text)
    
    # 2. Bảo vệ các chữ cái viết tắt tên riêng đơn lẻ (e.g. N.V. An -> N_ABBR_DOT_V_ABBR_DOT_ An)
    temp_text = re.sub(r'\b([a-zA-Z])\.', r'\1_ABBR_DOT_', temp_text)
    
    # 3. Bảo vệ các chữ viết tắt thông dụng kết thúc bằng dấu chấm
    abbrs = ["gs", "ts", "pgs", "ths", "tp", "dr", "mr", "mrs", "ms", "vs", "vol", "no", "prof", "tphcm", "co"]
    for abbr in abbrs:
        pattern = r'\b(' + abbr + r')\.'
        temp_text = re.sub(pattern, r'\1_ABBR_DOT_', temp_text, flags=re.IGNORECASE)
        
    # 4. Tách câu theo các dấu ngắt câu . ? ! theo sau bởi khoảng trắng (giữ lại dấu ngắt câu)
    raw_sentences = re.split(r'(?<=[.?!])\s+', temp_text)
    
    sentences = []
    for s in raw_sentences:
        s = s.strip()
        if not s:
            continue
        # Khôi phục các dấu chấm đã bảo vệ
        s = s.replace('_DECIMAL_DOT_', '.')
        s = s.replace('_ABBR_DOT_', '.')
        sentences.append(s)
        
    return sentences


def answer_question(
    question: str,
    top_k: int,
    db: Session,
    llm_service: LLMService,
    history: List[dict] = None,
    doc_ids: List[int] = None,
    user_id: int = None,
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

    indexed_count = doc_repo.count_indexed(user_id=user_id)
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
        target_docs = doc_repo.get_indexed(user_id=user_id)

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

    # Quyết định chế độ dựa trên tổng độ dài nội dung và giới hạn thực tế của LLM (tránh silent truncation)
    max_safe_chars = min(FULL_CONTEXT_THRESHOLD_CHARS, llm_service._max_content_chars)
    use_full_context = (
        combined_content
        and len(combined_content) <= max_safe_chars
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
        confidence_score = 1.0  # Full context = 100% tin cậy vì đọc hết tài liệu
        warning = None

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

        # ------------------------------------------------------------
        # Relevance threshold: kiểm tra max score trước khi gọi LLM
        # ------------------------------------------------------------
        max_score = max((r.score for r in search_results), default=0.0)

        if max_score < NO_CONTEXT_THRESHOLD:
            # Không có chunk nào đủ liên quan → trả fallback, không gọi LLM
            print(
                f"[RAG Mode] Max score {max_score:.3f} < NO_CONTEXT_THRESHOLD {NO_CONTEXT_THRESHOLD} "
                f"→ trả fallback, bỏ qua LLM generate."
            )
            answer = "Không tìm thấy thông tin liên quan trong tài liệu."
            context_chars = 0
            sources_for_response = []
            sources_for_db = []
            confidence_score = 0.0
            warning = None
        else:
            # Lọc chunk dưới RELEVANCE_THRESHOLD trước khi đưa vào context
            filtered_chunks = [r for r in search_results if r.score >= RELEVANCE_THRESHOLD]

            # Fallback: nếu sau lọc không còn chunk nào (tất cả đều ở giữa 2 ngưỡng)
            # → dùng toàn bộ search_results để không gọi LLM với context rỗng
            context_chunks = filtered_chunks if filtered_chunks else search_results

            if filtered_chunks:
                print(
                    f"[RAG Mode] {len(search_results)} chunks → giữ lại {len(filtered_chunks)} "
                    f"(score >= {RELEVANCE_THRESHOLD})"
                )
            else:
                print(
                    f"[RAG Mode] Tất cả {len(search_results)} chunks dưới threshold, "
                    f"dùng toàn bộ (fallback)."
                )

            context_chars = sum(len(r.chunk.text) for r in context_chunks)

            try:
                answer = llm_service.generate_answer(
                    question=question,
                    context_chunks=context_chunks,
                    history=history,
                )
            except RuntimeError:
                raise
            except Exception as e:
                raise RuntimeError(f"Lỗi sinh câu trả lời (RAG): {str(e)}")

            # Tính toán Confidence Score (weighted average của score)
            scores = [r.score for r in context_chunks]
            sum_scores = sum(scores)
            confidence_score = sum(s * s for s in scores) / sum_scores if sum_scores > 0 else 0.0

            # ------------------------------------------------------------
            # Hậu kiểm (Claim Verification)
            # ------------------------------------------------------------
            warning = None
            if hasattr(llm_service, "verify_claims"):
                # Lấy các câu trong answer làm claims dùng bộ chia câu thông minh
                claims = [c.strip() for c in split_into_sentences(answer) if len(c.strip()) > 10]
                if claims:
                    # Gộp toàn bộ context thành 1 chuỗi để verify
                    context_text = " ".join([r.chunk.text for r in context_chunks])
                    # Giới hạn context length cho NLI model (thường ~512 tokens -> ~2000 chars)
                    if len(context_text) > 2000:
                        context_text = context_text[:2000]
                        
                    nli_results = llm_service.verify_claims(context_text, claims)
                    
                    has_contradiction = False
                    for res in nli_results:
                        if not res:
                            continue
                        # Sắp xếp để lấy top 1 (argmax)
                        sorted_res = sorted(res, key=lambda x: x['score'], reverse=True)
                        if not sorted_res:
                            continue
                        
                        argmax_label = sorted_res[0]['label']
                        
                        if argmax_label == "contradiction":
                            has_contradiction = True
                            confidence_score -= 0.2
                        elif argmax_label == "neutral":
                            confidence_score -= 0.1
                            
                    if has_contradiction:
                        warning = "Một số thông tin trong câu trả lời có thể không chính xác so với tài liệu."
                        
                    # Đảm bảo điểm không bị âm
                    confidence_score = max(0.0, confidence_score)

            # Build sources
            sources_for_response = []
            sources_for_db = []
            seen = set()
            for r in context_chunks:
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
        user_id=user_id,
    )

    return AskResponse(
        question=question,
        answer=answer,
        sources=sources_for_response,
        model_used=llm_service._model_name,
        history_id=hist.id,
        mode=mode,
        context_chars=context_chars,
        confidence_score=round(confidence_score, 3),
        warning=warning,
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

    # map-reduce
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

BLOOM_PROMPTS = {
    "remember":   "Sinh câu hỏi yêu cầu nhớ lại CHÍNH XÁC định nghĩa, khái niệm, công thức từ tài liệu.",
    "understand": "Sinh câu hỏi yêu cầu giải thích bằng lời, so sánh hoặc phân loại khái niệm.",
    "apply":      "Sinh bài toán hoặc tình huống thực tế yêu cầu áp dụng kiến thức để giải quyết.",
    "analyze":    "Sinh câu hỏi phân tích nguyên nhân-kết quả, đánh giá ưu nhược điểm hoặc suy luận logic.",
}


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
    session_id: str = "default_user",
    bloom_level: str = None,
) -> QuizResponse:
    """
    Tạo bộ câu hỏi thi trắc nghiệm sử dụng Adaptive Learning (BKT).
    Chiến lược: tạo từng batch nhỏ 3 câu/lần để model nhỏ dễ tuân thủ JSON.
    """
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(doc_id)
    if not doc:
        raise ValueError(f"Không tìm thấy tài liệu ID={doc_id}")

    content_data = get_document_content(doc_id, doc_repo)
    if not content_data or not content_data["content"]:
        raise ValueError("Không thể đọc nội dung tài liệu")

    # Lấy weak chunks từ AdaptiveTutorService
    from ..services.adaptive_tutor_service import adaptive_tutor_service
    weak_chunk_ids = adaptive_tutor_service.get_weak_chunks(session_id, doc_id, db)

    # Pool size lớn hơn để có nhiều lựa chọn đa dạng (count * 3, tối thiểu 15)
    pool_size = max(15, count * 3)

    def _fetch_random_pool(size: int):
        """Lấy pool chunk ngẫu nhiên từ tài liệu, thử nhiều cách tên file."""
        chunks = llm_service.get_random_chunks(doc.file_name, count=size)
        if not chunks:
            extracted_name = Path(doc.file_path).stem + ".extracted.txt"
            chunks = llm_service.get_random_chunks(extracted_name, count=size)
        if not chunks:
            stem_name = Path(doc.file_name).stem
            chunks = llm_service.get_random_chunks_by_stem(stem_name, count=size)
        # ── GUARD: lọc bỏ chunk không thuộc đúng tài liệu ──
        if chunks:
            stem_lower = Path(doc.file_name).stem.lower()
            fname_lower = doc.file_name.lower()
            valid = [
                c for c in chunks
                if stem_lower in c.filename.lower()
                   or fname_lower in c.filename.lower()
            ]
            dropped = len(chunks) - len(valid)
            if dropped:
                print(
                    f"[Quiz GUARD] Loại bỏ {dropped} chunks không thuộc "
                    f"'{doc.file_name}' (last-resort trả về chunk sai)."
                )
            chunks = valid
        return chunks

    if weak_chunk_ids:
        print(f"[Adaptive Tutor] Tìm thấy {len(weak_chunk_ids)} chunks yếu.")
        # ── Mixed sampling: tối đa 50% từ weak, phần còn lại lấy random ──
        # Tránh BKT lock-in: không để weak chunks chiếm toàn bộ quiz mãi mãi.
        max_weak = max(1, count // 2)
        sampled_weak_ids = random.sample(weak_chunk_ids, min(max_weak, len(weak_chunk_ids)))
        weak_chunks = llm_service.get_chunks_by_ids(sampled_weak_ids)
        weak_id_set = {c.id for c in weak_chunks}
        print(f"[Adaptive Tutor] Dùng {len(weak_chunks)} weak chunks (≤50%), bổ sung random.")

        # Lấy random pool để bù phần còn lại
        random_pool = _fetch_random_pool(pool_size)
        extra_chunks = [c for c in random_pool if c.id not in weak_id_set]
        # Kết hợp và shuffle để câu hỏi không theo thứ tự cố định
        combined = weak_chunks + extra_chunks
        random.shuffle(combined)
        target_chunks = combined
    else:
        print(f"[Adaptive Tutor] User chưa có dữ liệu yếu, tạo ngẫu nhiên.")
        target_chunks = _fetch_random_pool(pool_size)
        if target_chunks:
            random.shuffle(target_chunks)

        print(f"[Quiz] Tìm được {len(target_chunks)} chunks hợp lệ cho '{doc.file_name}'.")

    all_questions: list = []
    batch_size = 3  # Tạo 3 câu/lần — model nhỏ dễ làm hơn
    q_index = 1

    # Nếu có chunks từ ChromaDB, sinh câu hỏi từ từng chunk
    if target_chunks:
        # Loop qua các chunk để sinh câu hỏi
        for chunk in target_chunks:
            if len(all_questions) >= count: break
            batch_qs = _generate_quiz_batch(
                llm_service=llm_service,
                content=chunk.text,
                filename=doc.file_name,
                batch_count=min(2, count - len(all_questions)),
                start_index=q_index,
                chunk_id=chunk.id,
                bloom_level=bloom_level,
            )
            all_questions.extend(batch_qs)
            q_index += len(batch_qs)
    else:
        # Fallback: không có chunk → chia nội dung thành các đoạn nhỏ, mỗi đoạn tạo batch
        full_content = content_data["content"]
        # Mỗi batch dùng đoạn nội dung 2500 ký tự riêng biệt
        segment_size = 2500
        segments = [full_content[i:i + segment_size] for i in range(0, len(full_content), segment_size)]
        print(f"[Quiz Fallback] Chia nội dung thành {len(segments)} đoạn, mỗi đoạn ~{segment_size} ký tự.")
        
        seg_index = 0
        for batch_start in range(0, count, batch_size):
            if seg_index >= len(segments):
                seg_index = 0  # Lặp lại nếu hết segment
            batch_count = min(batch_size, count - batch_start)
            batch_qs = _generate_quiz_batch(
                llm_service=llm_service,
                content=segments[seg_index],
                filename=doc.file_name,
                batch_count=batch_count,
                start_index=q_index,
                chunk_id="",
                bloom_level=bloom_level,
            )
            all_questions.extend(batch_qs)
            q_index += len(batch_qs)
            seg_index += 1
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
    chunk_id: str = "",
    bloom_level: str = None,
) -> list:
    """Tạo một batch nhỏ câu hỏi với Chain-of-Thought (CoT)."""

    MAX_QUIZ_CONTENT_CHARS = 2000  # Tăng từ 1200 → 2000 để AI thấy đủ nội dung đa dạng
    content_snippet = content[:MAX_QUIZ_CONTENT_CHARS]
    request_seed = random.randint(0, 2**31 - 1)

    bloom_instruction = ""
    if bloom_level and bloom_level in BLOOM_PROMPTS:
        bloom_instruction = f"""
YÊU CẦU VỀ CẤP ĐỘ NHẬN THỨC (BLOOM'S TAXONOMY):
- Cấp độ yêu cầu: {bloom_level.upper()}
- Hướng dẫn: {BLOOM_PROMPTS[bloom_level]}
- BẮT BUỘC tất cả câu hỏi được tạo ra trong batch này phải tuân thủ đúng yêu cầu nhận thức trên.
"""

    prompt = f"""Dưới đây là một đoạn văn. Hãy tạo đúng {batch_count} câu hỏi trắc nghiệm (A/B/C/D) dựa hoàn toàn vào nội dung đoạn văn này.
{bloom_instruction}
YÊU CẦU VỀ TOÁN HỌC:
1. Viết tất cả công thức, biểu thức, biến số toán học bằng LaTeX:
   - Inline: $x + y = C$, $u(x, y)$
   - Display: $$\\int_a^b f(x)\\,dx$$
2. KHÔNG sao chép ký tự bị lỗi font, hãy viết lại bằng LaTeX chuẩn.

YÊU CẦU VỀ NỘI DUNG:
- Mỗi câu hỏi phải kiểm tra một kiến thức khác nhau từ đoạn văn.
- Câu hỏi ngắn gọn, rõ ý, bám sát nội dung.
- KHÔNG đưa bất kỳ lời chào, lời dẫn, hay câu giới thiệu nào vào nội dung câu hỏi.

ĐOẠN VĂN:
{content_snippet}

Trả kết quả dưới dạng JSON array, mỗi phần tử là một object với các trường:
- "question": nội dung câu hỏi (không có số thứ tự hay lời dẫn)
- "options": object gồm 4 key "A", "B", "C", "D"
- "answer": một trong các giá trị "A", "B", "C", "D"
- "explanation": giải thích ngắn vì sao đáp án đúng
- "step_by_step_explanation": "<reasoning>Bước 1: ... Bước 2: ...</reasoning>"
- "bloom_level": một trong các giá trị "remember" (Nhớ), "understand" (Hiểu), "apply" (Vận dụng), "analyze" (Phân tích) để phân loại đúng cấp độ nhận thức của câu hỏi này.

Chỉ trả về JSON array, KHÔNG thêm bất kỳ văn bản nào khác trước hoặc sau."""

    try:
        raw = llm_service.chat_direct(
            prompt=prompt,
            system_prompt=(
                "Bạn là giáo viên. Hãy trả kết quả là một JSON array đúng định dạng. "
                "Không đưa bất kỳ lời chào, lời giới thiệu, lời cảm ơn hay văn bản thừa nào "
                "trước hoặc sau JSON. Bắt đầu bằng '[' và kết thúc bằng ']'."
            ),
            temperature=0.7,
            seed=request_seed,
        )
    except RuntimeError as e:
        err_str = str(e)
        if "Context size has been exceeded" in err_str or "400" in err_str:
            # Thử lại với nội dung ngắn hơn (500 ký tự)
            print(f"[Quiz] Context quá lớn, thử lại với nội dung 500 ký tự...")
            short_content = content[:500]
            short_prompt = (
                f"Tạo {batch_count} câu hỏi trắc nghiệm (A/B/C/D) từ đoạn văn sau. "
                f"Chỉ trả về JSON array, không thêm văn bản nào khác.\n\n"
                f"ĐOẠN VĂN:\n{short_content}"
            )
            raw = llm_service.chat_direct(
                prompt=short_prompt,
                system_prompt="Tạo câu hỏi trắc nghiệm tiếng Việt dạng JSON array. Không thêm bất kỳ văn bản nào khác.",
                temperature=0.7,
                seed=random.randint(0, 2**31 - 1),
            )
        else:
            raise

    # Làm sạch preamble của AI trước khi parse
    raw = _clean_ai_preamble(raw)

    # Thử JSON trước
    json_result = _try_parse_json(raw)
    if json_result:
        qs = [_normalize_question(q, start_index + i, default_bloom=bloom_level) for i, q in enumerate(json_result)]
        for q in qs:
            q.chunk_id = chunk_id
        return qs

    # Fallback: parse text thô (ít dùng vì đã ép JSON)
    qs = _parse_text_format(raw, start_index)
    for q in qs:
        q.chunk_id = chunk_id
        if not q.bloom_level:
            q.bloom_level = bloom_level or "remember"
    return qs


def _clean_ai_preamble(raw: str) -> str:
    """
    Xóa bỏ những phần 'rác' mà model nhỏ thường thêm vào:
    - Lời cảm ơn / xác nhận: "Tuyệt vời!", "Chắc chắn rồi!", "Dưới đây là..."
    - Markdown bold: **text**
    - Văn bản dưới dạng câu giới thiệu trước JSON array

    Chiến lược ưu tiên:
    1. Nếu output là ```json ... ``` block → lấy nội dung bên trong
    2. Nếu có JSON array `[` nào đó trong output → cắt từ `[` đầu tiên
    3. Nếu là text format "Câu N:" → cắt từ dòng câu hỏi đầu tiên
    4. Fallback: xóa markdown, giữ nguyên
    """
    # ── Bước 1: xử lý ```json ... ``` fenced block ──────────────────────────────────────
    fenced = re.search(r'```(?:json)?\s*\n?(.*?)```', raw, re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()

    # ── Bước 2: có dấu `[` → cắt bỏ mọi thứ trước nó ──────────────────────────────
    bracket_pos = raw.find('[')
    if bracket_pos > 0:  # > 0 nghĩa là có text trước `[`
        candidate = raw[bracket_pos:].strip()
        # Kiểm tra candidate có phải JSON hợp lệ không (tối thiểu là 1 object)
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, list):
                return candidate  # JSON hợp lệ, trả về
        except json.JSONDecodeError:
            pass  # Không hợp lệ, thử tìm cách khác

    # ── Bước 3: text format "Câu N:" → cắt từ dòng câu hỏi đầu tiên ─────────────────
    lines = raw.splitlines()
    result_lines = []
    found_first_question = False

    question_start = re.compile(
        r'^(?:Câu\s*\d+[:\.]|\*\*Câu\s*\d+\*\*|Question\s*\d+[:\.]|\d+[\.)\:])',
        re.IGNORECASE
    )

    for line in lines:
        if question_start.match(line.strip()):
            found_first_question = True
        if found_first_question:
            clean = re.sub(r'\*\*(.+?)\*\*', r'\1', line)
            clean = re.sub(r'\*(.+?)\*', r'\1', clean)
            clean = re.sub(r'__(.+?)__', r'\1', clean)
            result_lines.append(clean)

    # ── Bước 4: fallback — xóa markdown, giữ nguyên ──────────────────────────────────────
    if not result_lines:
        cleaned = re.sub(r'\*\*(.+?)\*\*', r'\1', raw)
        cleaned = re.sub(r'\*(.+?)\*', r'\1', cleaned)
        return cleaned

    return '\n'.join(result_lines)


def _clean_question_text(text: str) -> str:
    """
    Làm sạch text câu hỏi:
    - Xóa các câu giới thiệu/lời dẫn/lời chào của AI (preamble)
    - Xóa prefix 'Câu N:' nếu sót lại trong nội dung
    - Xóa markdown bold/italic
    - Strip khoảng trắng thừa
    """
    text = text.strip()
    if not text:
        return ""

    # Normalize cases where "Câu hỏi 1:" is embedded inside a sentence without proper period separation
    # e.g., "Dưới đây là câu hỏi: Câu hỏi 1: Hãy chọn..." -> "Dưới đây là câu hỏi. Câu hỏi 1: Hãy chọn..."
    text = re.sub(r'([^.!?\n\s])\s+(Câu\s*hỏi\s*\d+|Câu\s*\d+|Question\s*\d+)([:\.\s\-])', r'\1. \2\3', text, flags=re.IGNORECASE)

    # Split the text into parts (sentences or clauses) by periods, exclamation marks, or question marks followed by space
    parts = re.split(r'([\.!\?]\s+)', text)
    
    # Reconstruct sentences
    sentences = []
    current = ""
    for part in parts:
        if re.match(r'^[\.!\?]\s+$', part):
            current += part.strip()
            sentences.append(current)
            current = ""
        else:
            current += part
    if current:
        sentences.append(current)

    cleaned_sentences = []
    is_preamble_phase = True

    # Preamble trigger words/phrases (case insensitive)
    excl_patterns = [
        r'^(tuyệt vời|chắc chắn rồi|tất nhiên|tất nhiên rồi|chào bạn|ok|được chứ|tất nhiên là được)[!\.\s]*$',
        r'^(dưới đây|sau đây|đây) là\s+(?:các|một số|câu hỏi|bộ câu hỏi)[^!\.\?]*$',
        r'^tôi xin gửi[^!\.\?]*$',
        r'^theo yêu cầu của bạn[^!\.\?]*$',
    ]

    def is_preamble(sentence: str) -> bool:
        s = sentence.lower().strip()
        # Clean trailing punctuation for easier matching
        s_clean = re.sub(r'[\.!\?:\s]+$', '', s).strip()
        if not s_clean:
            return True
        
        # If it matches any standalone pattern
        for pat in excl_patterns:
            if re.match(pat, s_clean):
                return True
        
        # Check if sentence contains AI action + quiz reference
        has_ai = any(w in s_clean for w in ["tôi sẽ", "tôi đã", "tôi xin", "sẽ tạo", "sẽ giúp", "tôi tạo", "tạo ra", "sinh ra", "thiết lập", "cung cấp câu hỏi", "gửi đến bạn", "tôi gửi"])
        has_quiz = any(w in s_clean for w in ["câu hỏi", "trắc nghiệm", "đáp án", "lựa chọn", "quiz", "bài tập"])
        if has_ai and has_quiz:
            return True

        # Check if sentence references "đoạn văn bạn cung cấp" or "tài liệu" or "yêu cầu"
        has_source = any(w in s_clean for w in ["bạn cung cấp", "bạn đã gửi", "đoạn văn trên", "văn bản trên", "tài liệu trên", "nội dung trên", "yêu cầu của bạn"])
        if has_source and (has_quiz or has_ai or "dưới đây" in s_clean or "sau đây" in s_clean):
            return True
            
        # Check if it starts with "dưới đây là" or "sau đây là" and contains "câu hỏi" / "trắc nghiệm"
        if (s_clean.startswith("dưới đây là") or s_clean.startswith("sau đây là")) and any(w in s_clean for w in ["câu hỏi", "trắc nghiệm", "đáp án", "lựa chọn", "bộ đề", "bài tập"]):
            return True

        return False

    for sentence in sentences:
        if is_preamble_phase:
            if is_preamble(sentence):
                # Skip this sentence as it's a preamble
                continue
            else:
                is_preamble_phase = False
                cleaned_sentences.append(sentence)
        else:
            cleaned_sentences.append(sentence)

    cleaned_text = " ".join(cleaned_sentences).strip()

    # Clean up prefix like "Câu hỏi 1:", "Câu 1:", "Question 1:", "Câu hỏi:"
    cleaned_text = re.sub(
        r'^(?:Câu\s*hỏi\s*\d+[:\.\s\-]*|Câu\s*\d+[:\.\s\-]*|Question\s*\d+[:\.\s\-]*|Câu\s*hỏi[:\.\s\-]*|Câu\s*hỏi\s*thứ\s*\w+[:\.\s\-]*)',
        '',
        cleaned_text,
        flags=re.IGNORECASE
    )

    # Strip markdown bold/italic
    cleaned_text = re.sub(r'\*\*(.+?)\*\*', r'\1', cleaned_text)
    cleaned_text = re.sub(r'\*(.+?)\*', r'\1', cleaned_text)
    cleaned_text = re.sub(r'__(.+?)__', r'\1', cleaned_text)

    # Fallback to avoid empty output
    if not cleaned_text.strip():
        basic_clean = re.sub(
            r'^(?:Câu\s*hỏi\s*\d+[:\.\s\-]*|Câu\s*\d+[:\.\s\-]*|Question\s*\d+[:\.\s\-]*)',
            '',
            text,
            flags=re.IGNORECASE
        )
        return basic_clean.strip()

    return cleaned_text.strip()


_LONE_BACKSLASH_RE = re.compile(r'(?<!\\)\\(?!(?:["\\/]|[ntrbf](?![a-zA-Z])|u[0-9a-fA-F]{4}))')


def _sanitize_json_backslashes(text: str) -> str:
    """Escape lone backslashes that are not valid JSON escape sequences.
    
    LLMs often emit LaTeX like \\frac inside JSON strings as a single backslash
    (\\frac), which is an invalid JSON escape.  We double every backslash that
    is NOT already part of a recognised JSON escape sequence so that json.loads
    can parse the result.
    """
    return _LONE_BACKSLASH_RE.sub(r'\\\\', text)


def _try_parse_json(raw: str) -> list:
    """Thử parse JSON từ response. Trả None nếu thất bại."""
    raw = raw.strip()

    def _loads(s: str):
        """Try json.loads on the original string, then on the backslash-sanitized version."""
        try:
            return json.loads(s)
        except Exception:
            pass
        try:
            return json.loads(_sanitize_json_backslashes(s))
        except Exception:
            return None

    # 1. Thử parse thẳng
    data = _loads(raw)
    if isinstance(data, list) and data:
        return data

    # 2. Tìm theo markdown codeblock ```json ... ```
    md_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', raw, re.DOTALL)
    if md_match:
        data = _loads(md_match.group(1))
        if isinstance(data, list) and data:
            return data

    # 3. Quét ngược từ dấu ] cuối cùng (Bypass lỗi LaTeX '}' ngay trước ']')
    start_idx = raw.find('[')
    if start_idx != -1:
        pos = raw.rfind(']')
        while pos > start_idx:
            candidate = raw[start_idx:pos+1]
            data = _loads(candidate)
            if isinstance(data, list) and data:
                return data
            pos = raw.rfind(']', start_idx, pos)

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
                    correct_option=answer,
                    explanation=expl,
                ))
            i = j
        else:
            i += 1

    return questions


def _normalize_question(q: dict, idx: int, default_bloom: str = None) -> QuizQuestion:
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

    bloom = str(q.get("bloom_level", "")).strip().lower()
    if bloom not in ["remember", "understand", "apply", "analyze"]:
        bloom = default_bloom if default_bloom in ["remember", "understand", "apply", "analyze"] else "remember"

    return QuizQuestion(
        id=idx,
        question=_clean_question_text(str(q.get("question", f"Câu hỏi {idx}"))),
        options=options,
        answer=answer,
        correct_option=answer,
        explanation=str(q.get("explanation", "")),
        step_by_step_explanation=str(q.get("step_by_step_explanation", "")),
        chunk_id="",
        bloom_level=bloom
    )




def generate_learning_path(
    doc_id: int,
    session_id: str,
    wrong_chunk_ids: List[str],
    db: Session,
    llm_service: LLMService,
) -> LearningPathResponse:
    """
    Tao lo trinh hoc tap ca nhan hoa.
    Chien luoc:
    - Gop toan bo ngu canh chunk yeu + BKT score vao 1 prompt duy nhat
    - Sap xep chunk theo BKT (yeu nhat len dau)
    - Goi AI 1 lan, yeu cau tra ve JSON Array co hanh dong cu the
    - Parse JSON, map lai chunk_meta, fallback neu AI loi
    """
    from ..services.adaptive_tutor_service import adaptive_tutor_service
    from ..models.domain import UserKnowledge

    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(doc_id)
    if not doc:
        raise ValueError(f"Khong tim thay tai lieu ID={doc_id}")

    # 1. Tong hop chunk_ids can xem lai (wrong + BKT weak)
    bkt_weak_ids = adaptive_tutor_service.get_weak_chunks(session_id, doc_id, db)
    all_weak_ids = list(dict.fromkeys(wrong_chunk_ids + bkt_weak_ids))

    if not all_weak_ids:
        return LearningPathResponse(
            doc_id=doc_id,
            file_name=doc.file_name,
            items=[],
            total_weak=0,
            overall_message=(
                "Ban da lam bai nhung chua co du du lieu de tao lo trinh. "
                "Hay lam them bai de he thong hieu diem manh/yeu cua ban!"
            ),
        )

    # 2. Lay noi dung cac chunk tu ChromaDB
    chunks = llm_service.get_chunks_by_ids(all_weak_ids)
    if not chunks:
        stem_name = Path(doc.file_name).stem
        chunks = llm_service.get_random_chunks_by_stem(
            stem_name, count=min(len(all_weak_ids), 5)
        )

    # 3. Lay BKT probability cho tung chunk
    bkt_map: dict = {}
    try:
        knowledge_records = db.query(UserKnowledge).filter(
            UserKnowledge.session_id == session_id,
            UserKnowledge.doc_id == doc_id,
        ).all()
        bkt_map = {k.chunk_id: k.probability for k in knowledge_records}
    except Exception:
        pass

    # 4. Sap xep chunks: yeu nhat (BKT thap nhat) len dau, gioi han 6
    chunks_to_use = sorted(
        chunks[:6],
        key=lambda c: bkt_map.get(c.id, 50)
    )

    # 5. Gop ngu canh va luu meta
    aggregated_parts = []
    chunk_meta = []
    for i, chunk in enumerate(chunks_to_use, 1):
        bkt_prob = bkt_map.get(chunk.id, 0)
        snippet = chunk.text[:600]
        aggregated_parts.append(
            f"[Phan {i} - Diem hieu bai: {bkt_prob}%]:\n{snippet}"
        )
        chunk_meta.append({
            "chunk_id": chunk.id,
            "bkt_probability": bkt_prob,
            "snippet": snippet,
        })

    aggregated_context = "\n\n---\n\n".join(aggregated_parts)

    # 6. Prompt Chain-of-Thought (Actionable) - goi AI 1 lan
    json_schema = (
        "[\n"
        "  {\n"
        '    \"topic\": \"Ten chu de ngan gon (5-10 tu)\",\n'
        '    \"advice\": \"[TAI SAO] Giai thich ly do can on. [HANH DONG] 1. ... 2. ... 3. ...\"\n'
        "  }\n"
        "]"
    )

    roadmap_prompt = (
        f"Ban la chuyen gia thiet ke lo trinh hoc tap ca nhan hoa.\n"
        f"Duoi day la cac phan kien thuc nguoi hoc dang yeu tu tai lieu '{doc.file_name}',"
        f" kem Diem hieu bai (0%=khong hieu, 100%=hieu hoan toan):\n\n"
        f"{aggregated_context}\n\n"
        f"Nhiem vu:\n"
        f"1. Phan tich tong the cac lo hong kien thuc.\n"
        f"2. Sap xep uu tien: phan nen tang hoac diem thap nhat hoc truoc.\n"
        f"3. Moi buoc phai co [TAI SAO] va [HANH DONG] it nhat 2 hanh dong cu the.\n\n"
        f"Tra ve JSON Array theo dung mau sau, KHONG them gi khac:\n"
        f"{json_schema}"
    )

    system_prompt = (
        "Ban la gia su giao duc. Tra ve JSON Array lo trinh hoc tap bang tieng Viet, "
        "moi phan tu co topic va advice co hanh dong cu the. KHONG them van ban nao ngoai JSON."
    )

    print(
        f"[LearningPath] Goi AI 1 lan voi {len(chunks_to_use)} chunk, "
        f"~{len(aggregated_context)} ky tu."
    )

    # 7. Goi LLM 1 lan - parse JSON - fallback neu loi
    items: List[LearningPathItem] = []
    try:
        raw = llm_service.chat_direct(prompt=roadmap_prompt, system_prompt=system_prompt)

        parsed = None
        try:
            parsed = json.loads(raw.strip())
        except Exception:
            pass

        if not isinstance(parsed, list):
            for pat in [
                r'\[\s*\{.*?\}\s*\]',
                r'```(?:json)?\s*(\[.*?\])\s*```',
            ]:
                m = re.search(pat, raw, re.DOTALL)
                if m:
                    try:
                        parsed = json.loads(m.group(1) if m.lastindex else m.group())
                        break
                    except Exception:
                        pass

        if isinstance(parsed, list) and parsed:
            for i, item_data in enumerate(parsed):
                meta = chunk_meta[i] if i < len(chunk_meta) else {}
                items.append(LearningPathItem(
                    topic=str(item_data.get("topic", f"Chu de {i+1}")).strip(),
                    content_snippet=meta.get("snippet", ""),
                    advice=str(item_data.get("advice", "Hay doc lai doan nay ky hon.")).strip(),
                    bkt_probability=meta.get("bkt_probability", 0),
                    chunk_id=meta.get("chunk_id", ""),
                ))
            print(f"[LearningPath] Tao thanh cong {len(items)} buoc lo trinh.")
        else:
            raise ValueError("AI khong tra ve JSON hop le")

    except Exception as e:
        print(f"[LearningPath] Fallback do loi: {e}")
        for i, meta in enumerate(chunk_meta):
            items.append(LearningPathItem(
                topic=f"Chu de can on #{i + 1}",
                content_snippet=meta["snippet"],
                advice=(
                    f"[TAI SAO] Phan nay co diem hieu bai {meta['bkt_probability']}% - can cu co."
                    f" [HANH DONG] 1. Doc ky doan trich dan tren."
                    f" 2. Tom tat lai y chinh bang loi cua ban."
                    f" 3. Thu tra loi cau hoi lien quan den doan nay."
                ),
                bkt_probability=meta["bkt_probability"],
                chunk_id=meta["chunk_id"],
            ))

    # 8. Nhan xet tong the
    n_weak = len(all_weak_ids)
    if n_weak == 0:
        overall = "Xuat sac! Ban nam vung tat ca kien thuc."
    elif n_weak <= 2:
        overall = (
            f"Gan duoc roi! Ban chi con {n_weak} chu de can cu co. "
            f"Hay on lai theo lo trinh duoi."
        )
    elif n_weak <= 5:
        overall = (
            f"Ban co {n_weak} chu de can on them. "
            f"Hay xem lai tung muc theo thu tu duoi, bat dau tu phan diem thap nhat."
        )
    else:
        overall = (
            f"Co {n_weak} chu de can on. "
            f"Dung nan - hay hoc tung buoc mot theo lo trinh duoi!"
        )

    return LearningPathResponse(
        doc_id=doc_id,
        file_name=doc.file_name,
        items=items,
        total_weak=n_weak,
        overall_message=overall,
    )
