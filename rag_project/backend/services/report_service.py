import os
import urllib.request
from datetime import datetime
from pathlib import Path
from fpdf import FPDF
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models.domain import Document, UserKnowledge, QuizHistory
from ..repositories.document_repo import DocumentRepository
from ..services.llm_service import LLMService

def get_font_paths():
    """Tải font Roboto hỗ trợ tiếng Việt Unicode từ CDN Google Fonts lưu cục bộ."""
    font_dir = Path(__file__).parent / "fonts"
    font_dir.mkdir(exist_ok=True)
    
    regular_path = font_dir / "Roboto-Regular.ttf"
    bold_path = font_dir / "Roboto-Bold.ttf"
    
    # Download Roboto-Regular if not exists
    if not regular_path.exists():
        try:
            url = "https://cdn.jsdelivr.net/gh/google/fonts@main/apache/roboto/static/Roboto-Regular.ttf"
            print(f"[PDF Font] Đang tải font Roboto-Regular từ {url}...")
            urllib.request.urlretrieve(url, regular_path)
        except Exception as e:
            print(f"[PDF Font] Lỗi tải font Roboto-Regular: {e}")
            
    # Download Roboto-Bold if not exists
    if not bold_path.exists():
        try:
            url = "https://cdn.jsdelivr.net/gh/google/fonts@main/apache/roboto/static/Roboto-Bold.ttf"
            print(f"[PDF Font] Đang tải font Roboto-Bold từ {url}...")
            urllib.request.urlretrieve(url, bold_path)
        except Exception as e:
            print(f"[PDF Font] Lỗi tải font Roboto-Bold: {e}")
            
    res = {}
    if regular_path.exists():
        res["regular"] = str(regular_path)
    else:
        windows_font = Path("C:/Windows/Fonts/arial.ttf")
        if windows_font.exists():
            res["regular"] = str(windows_font)
            
    if bold_path.exists():
        res["bold"] = str(bold_path)
    else:
        windows_font_bold = Path("C:/Windows/Fonts/arialbd.ttf")
        if windows_font_bold.exists():
            res["bold"] = str(windows_font_bold)
            
    return res


class LearningReportPDF(FPDF):
    def header(self):
        # Draw a top bar
        self.set_fill_color(16, 185, 129) # Emerald Green
        self.rect(0, 0, 210, 8, "F")
        
    def footer(self):
        self.set_y(-15)
        # Use Roboto if registered, else Helvetica
        font_name = "Roboto" if "Roboto" in self.fonts else "Helvetica"
        self.set_font(font_name, "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Trang {self.page_no()}/{{nb}} - Báo cáo Học tập Cá nhân hóa RAG Smart Document Reader", align="C")


class ReportService:
    @staticmethod
    def get_report_data(doc_id: int, user_id: int, db: Session, llm_service: LLMService) -> dict:
        """Tổng hợp dữ liệu học tập của user cho tài liệu cụ thể."""
        doc_repo = DocumentRepository(db)
        doc = doc_repo.get_by_id(doc_id)
        if not doc:
            raise ValueError(f"Không tìm thấy tài liệu ID={doc_id}")
            
        # 1. Tải toàn bộ chunks của tài liệu từ ChromaDB
        stem = Path(doc.file_name).stem
        raw_results = llm_service._get_embeddings_for_doc(doc.file_name, stem)
        total_chunks = len(raw_results.get("ids", []))
        
        # 2. Lấy dữ liệu BKT (UserKnowledge)
        knowledges = db.query(UserKnowledge).filter(
            UserKnowledge.doc_id == doc_id,
            UserKnowledge.session_id == str(user_id)
        ).all()
        knowledge_map = {k.chunk_id: k.probability for k in knowledges}
        
        # Build full chunks list with BKT info
        chunks_list = []
        for i in range(total_chunks):
            cid = raw_results["ids"][i]
            txt = raw_results["documents"][i]
            prob = knowledge_map.get(cid, 50) # Mặc định 50% nếu chưa học
            chunks_list.append({"id": cid, "text": txt, "probability": prob})
            
        # Tính tiến trình tổng quan (% chunk đã nắm vững >= 80)
        mastered_count = sum(1 for c in chunks_list if c["probability"] >= 80)
        overall_progress = round(mastered_count * 100 / total_chunks) if total_chunks > 0 else 0
        
        # Phân loại strengths & weaknesses
        strengths_raw = sorted([c for c in chunks_list if c["probability"] >= 80], key=lambda x: x["probability"], reverse=True)[:5]
        weaknesses_raw = sorted([c for c in chunks_list if c["probability"] < 60], key=lambda x: x["probability"])[:5]
        
        strengths = []
        for c in strengths_raw:
            clean_t = " ".join(c["text"].split())
            topic = clean_t[:60] + "..." if len(clean_t) > 60 else clean_t
            strengths.append({"id": c["id"], "topic": topic, "probability": c["probability"]})
            
        weaknesses = []
        for c in weaknesses_raw:
            clean_t = " ".join(c["text"].split())
            topic = clean_t[:60] + "..." if len(clean_t) > 60 else clean_t
            weaknesses.append({"id": c["id"], "topic": topic, "probability": c["probability"]})
            
        # 3. Lấy dữ liệu QuizHistory
        history = db.query(QuizHistory).filter(
            QuizHistory.doc_id == doc_id,
            QuizHistory.session_id == str(user_id)
        ).all()
        
        total_qs = len(history)
        correct_qs = sum(1 for h in history if h.is_correct == 1)
        accuracy = round(correct_qs / total_qs, 2) if total_qs > 0 else 0.0
        
        # Tính toán Bloom breakdown
        bloom_levels = ["remember", "understand", "apply", "analyze"]
        bloom_stats = {}
        for lvl in bloom_levels:
            lvl_records = [h for h in history if h.bloom_level == lvl]
            lvl_total = len(lvl_records)
            lvl_correct = sum(1 for h in lvl_records if h.is_correct == 1)
            lvl_acc = round(lvl_correct / lvl_total, 2) if lvl_total > 0 else 0.0
            bloom_stats[lvl] = {
                "correct": lvl_correct,
                "total": lvl_total,
                "accuracy": lvl_acc
            }
            
        # 4. Tự động sinh câu hỏi ôn tập dựa trên các weak chunks
        recommended_review = []
        if weaknesses_raw:
            recommended_review = ReportService._generate_review_questions_for_weaknesses(weaknesses_raw, llm_service)
            
        return {
            "doc_name": doc.file_name,
            "overall_summary": doc.summary or "Tài liệu chưa được tóm tắt.",
            "overall_progress": overall_progress,
            "total_chunks": total_chunks,
            "mastered_chunks": mastered_count,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "quiz_stats": {
                "total": total_qs,
                "correct": correct_qs,
                "accuracy": accuracy
            },
            "bloom_stats": bloom_stats,
            "recommended_review": recommended_review
        }

    @staticmethod
    def _generate_review_questions_for_weaknesses(weak_chunks: list, llm_service: LLMService) -> list:
        """Sử dụng LLM sinh ra 1 câu hỏi trắc nghiệm ôn tập cho mỗi chunk yếu (tối đa 5 câu)."""
        from ..services.rag_service import _clean_ai_preamble, _try_parse_json
        
        parts = []
        for idx, chunk in enumerate(weak_chunks, 1):
            parts.append(f"[Đoạn {idx} - ID: {chunk['id']}]:\n{chunk['text'][:800]}")
        context = "\n\n---\n\n".join(parts)
        
        prompt = f"""Dưới đây là {len(weak_chunks)} đoạn văn bản từ tài liệu học tập. Với mỗi đoạn văn bản, hãy tạo đúng 1 câu hỏi trắc nghiệm (A/B/C/D) phù hợp nhất để kiểm tra kiến thức của đoạn đó.

Yêu cầu:
1. Viết tất cả công thức toán học bằng LaTeX (ví dụ: $x^2$, $$\\frac{{a}}{{b}}$$).
2. Định dạng trả về phải là một JSON array, mỗi phần tử là một object gồm:
   - "question": nội dung câu hỏi
   - "options": object gồm "A", "B", "C", "D"
   - "answer": đáp án đúng ("A" hoặc "B" hoặc "C" hoặc "D")
   - "explanation": giải thích ngắn gọn lý do chọn đáp án đó

ĐOẠN VĂN BẢN:
{context}

Chỉ trả về duy nhất JSON array, KHÔNG thêm bất kỳ giải thích hay text nào khác."""

        try:
            raw = llm_service.chat_direct(
                prompt=prompt,
                system_prompt="Bạn là giáo viên thiết kế đề ôn tập. Hãy trả kết quả là một JSON array đúng định dạng. Bắt đầu bằng '[' và kết thúc bằng ']'.",
                temperature=0.3
            )
            raw = _clean_ai_preamble(raw)
            parsed = _try_parse_json(raw)
            if parsed and isinstance(parsed, list):
                questions = []
                for idx, q in enumerate(parsed[:len(weak_chunks)]):
                    questions.append({
                        "chunk_id": weak_chunks[idx]["id"],
                        "question": q.get("question", ""),
                        "options": q.get("options", {"A": "", "B": "", "C": "", "D": ""}),
                        "answer": q.get("answer", "A"),
                        "explanation": q.get("explanation", "")
                    })
                return questions
        except Exception as e:
            print(f"[WARN] Lỗi tự động tạo câu hỏi ôn tập: {e}")
            
        return []

    @staticmethod
    def generate_pdf(report_data: dict) -> bytes:
        """Vẽ file PDF báo cáo học tập 4 trang bằng fpdf2."""
        font_paths = get_font_paths()
        pdf = LearningReportPDF(orientation="P", unit="mm", format="A4")
        pdf.alias_nb_pages()
        
        font_name = "Helvetica"
        if "regular" in font_paths:
            try:
                pdf.add_font("Roboto", style="", fname=font_paths["regular"])
                if "bold" in font_paths:
                    pdf.add_font("Roboto", style="B", fname=font_paths["bold"])
                font_name = "Roboto"
            except Exception as e:
                print(f"[PDF] Lỗi add_font: {e}")
                
        # --- TRANG 1: TRANG BÌA & TÓM TẮT TÀI LIỆU ---
        pdf.add_page()
        pdf.set_y(25)
        
        # Tiêu đề báo cáo
        pdf.set_font(font_name, "B", 24)
        pdf.set_text_color(16, 185, 129) # Emerald
        pdf.cell(0, 10, "BÁO CÁO KẾT QUẢ HỌC TẬP", align="C", ln=True)
        pdf.set_font(font_name, "B", 12)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 10, "Hệ thống RAG Smart Document Reader", align="C", ln=True)
        pdf.ln(10)
        
        # Meta info box
        pdf.set_fill_color(240, 240, 240)
        pdf.rect(15, 50, 180, 25, "F")
        pdf.set_y(52)
        pdf.set_x(20)
        pdf.set_font(font_name, "B", 10)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(0, 5, f"Tên tài liệu: {report_data['doc_name']}", ln=True)
        pdf.set_x(20)
        pdf.cell(0, 5, f"Thời gian lập báo cáo: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", ln=True)
        pdf.set_x(20)
        pdf.cell(0, 5, f"Tổng số phân đoạn (Chunks): {report_data['total_chunks']} chunks", ln=True)
        pdf.ln(20)
        
        # Tóm tắt tài liệu
        pdf.set_font(font_name, "B", 14)
        pdf.set_text_color(16, 185, 129)
        pdf.cell(0, 10, "1. Tóm tắt nội dung tài liệu tổng quan (AI Summary)", ln=True)
        pdf.ln(3)
        pdf.set_font(font_name, "", 10)
        pdf.set_text_color(60, 60, 60)
        # multi_cell tự động xuống dòng
        pdf.multi_cell(0, 6, report_data["overall_summary"])
        
        # --- TRANG 2: MA TRẬN KIẾN THỨC BKT ---
        pdf.add_page()
        pdf.set_y(20)
        pdf.set_font(font_name, "B", 14)
        pdf.set_text_color(16, 185, 129)
        pdf.cell(0, 10, "2. Tiến trình học tập & Ma trận Kiến thức (BKT)", ln=True)
        pdf.ln(5)
        
        # Progress status bar
        pdf.set_font(font_name, "", 11)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(0, 8, f"Mức độ thành thạo tài liệu tổng quát: {report_data['overall_progress']}%", ln=True)
        # Draw progress bar
        pdf.set_draw_color(220, 220, 220)
        pdf.set_fill_color(240, 240, 240)
        pdf.rect(15, 38, 180, 5, "DF")
        pdf.set_fill_color(16, 185, 129)
        progress_w = int(180 * report_data["overall_progress"] / 100)
        if progress_w > 0:
            pdf.rect(15, 38, progress_w, 5, "F")
        pdf.ln(12)
        
        # Strengths Section (Đã nắm vững)
        pdf.set_font(font_name, "B", 12)
        pdf.set_text_color(16, 185, 129)
        pdf.cell(0, 8, "Chuyên đề đã nắm vững (Strengths - BKT >= 80%):", ln=True)
        pdf.ln(2)
        pdf.set_font(font_name, "", 10)
        pdf.set_text_color(50, 50, 50)
        if not report_data["strengths"]:
            pdf.cell(0, 8, "Chưa có chủ đề nào đạt mức độ thấu hiểu >= 80%. Hãy luyện tập thêm!", ln=True)
        else:
            for idx, s in enumerate(report_data["strengths"], 1):
                pdf.cell(0, 7, f"  {idx}. {s['topic']} (Mức độ hiểu: {s['probability']}%)", ln=True)
        pdf.ln(10)
        
        # Weaknesses Section (Lỗ hổng kiến thức)
        pdf.set_font(font_name, "B", 12)
        pdf.set_text_color(225, 29, 72) # Rose color
        pdf.cell(0, 8, "Lỗ hổng kiến thức cần ôn tập (Weaknesses - BKT < 60%):", ln=True)
        pdf.ln(2)
        pdf.set_font(font_name, "", 10)
        pdf.set_text_color(50, 50, 50)
        if not report_data["weaknesses"]:
            pdf.cell(0, 8, "Chúc mừng! Bạn đã nắm bắt tốt tài liệu và không có phần kiến thức nào yếu dưới 60%.", ln=True)
        else:
            for idx, w in enumerate(report_data["weaknesses"], 1):
                pdf.cell(0, 7, f"  {idx}. {w['topic']} (Mức độ hiểu: {w['probability']}%)", ln=True)
                
        # --- TRANG 3: THỐNG KÊ QUIZ & BLOOM ---
        pdf.add_page()
        pdf.set_y(20)
        pdf.set_font(font_name, "B", 14)
        pdf.set_text_color(16, 185, 129)
        pdf.cell(0, 10, "3. Thống kê kết quả luyện tập (Quiz Statistics)", ln=True)
        pdf.ln(5)
        
        # Quiz Stats Info
        qs_total = report_data["quiz_stats"]["total"]
        qs_correct = report_data["quiz_stats"]["correct"]
        qs_acc = round(report_data["quiz_stats"]["accuracy"] * 100)
        
        pdf.set_font(font_name, "", 11)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(0, 8, f"Tổng số câu hỏi đã làm: {qs_total} câu", ln=True)
        pdf.cell(0, 8, f"Số câu trả lời đúng: {qs_correct} câu", ln=True)
        pdf.cell(0, 8, f"Tỷ lệ chính xác tổng thể: {qs_acc}%", ln=True)
        pdf.ln(10)
        
        # Bloom's Taxonomy breakdown
        pdf.set_font(font_name, "B", 12)
        pdf.set_text_color(16, 185, 129)
        pdf.cell(0, 8, "Kết quả phân tích theo cấp độ nhận thức Bloom:", ln=True)
        pdf.ln(3)
        
        bloom_names = {
            "remember": "🔵 Nhận biết (Remember)",
            "understand": "🟣 Thông hiểu (Understand)",
            "apply": "🟠 Vận dụng (Apply)",
            "analyze": "🔴 Vận dụng cao / Phân tích (Analyze)"
        }
        
        pdf.set_font(font_name, "", 10)
        for level, info in report_data["bloom_stats"].items():
            level_name = bloom_names.get(level, level.capitalize())
            pct = round(info["accuracy"] * 100)
            pdf.set_text_color(50, 50, 50)
            pdf.cell(80, 8, f"  {level_name}:")
            pdf.set_text_color(100, 100, 100)
            pdf.cell(40, 8, f"{info['correct']}/{info['total']} câu đúng")
            pdf.set_font(font_name, "B", 10)
            pdf.set_text_color(16, 185, 129) if pct >= 80 else pdf.set_text_color(225, 29, 72) if pct < 60 else pdf.set_text_color(245, 158, 11)
            pdf.cell(30, 8, f"{pct}%", ln=True)
            pdf.set_font(font_name, "", 10)
            
        # --- TRANG 4: ĐỀ CÂU HỎI LUYỆN TẬP ĐỀ XUẤT ---
        pdf.add_page()
        pdf.set_y(20)
        pdf.set_font(font_name, "B", 14)
        pdf.set_text_color(16, 185, 129)
        pdf.cell(0, 10, "4. Đề ôn tập cá nhân hóa đề xuất (Review Exercises)", ln=True)
        pdf.ln(5)
        
        if not report_data["recommended_review"]:
            pdf.set_font(font_name, "", 10)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 8, "Không có câu hỏi đề xuất mới. Bạn đã thấu hiểu tốt tất cả các chunk kiến thức!", ln=True)
        else:
            pdf.set_font(font_name, "", 10)
            for idx, q in enumerate(report_data["recommended_review"], 1):
                pdf.set_font(font_name, "B", 10)
                pdf.set_text_color(50, 50, 50)
                pdf.cell(0, 7, f"Câu {idx}: {q['question']}", ln=True)
                pdf.set_font(font_name, "", 10)
                pdf.set_text_color(80, 80, 80)
                
                # Options
                for opt_key, opt_val in q["options"].items():
                    pdf.cell(0, 6, f"  {opt_key}. {opt_val}", ln=True)
                
                # Correct Answer & Explanation
                pdf.set_font(font_name, "I", 9)
                pdf.set_text_color(16, 185, 129)
                pdf.cell(0, 6, f"  → Đáp án đúng: {q['answer']} | Giải thích: {q['explanation']}", ln=True)
                pdf.ln(4)
                pdf.set_font(font_name, "", 10)
                
        # Trả về file PDF dạng bytes
        return bytes(pdf.output())
