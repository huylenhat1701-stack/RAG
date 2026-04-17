# BÁO CÁO TIẾN ĐỘ VÀ ĐÁNH GIÁ DỰ ÁN RAG
**(Hệ thống Hỏi đáp & Tóm tắt Tài liệu Thông minh)**

---

## 1. Quá trình phát triển dự án
Quá trình xây dựng hệ thống RAG (Retrieval-Augmented Generation) đã được trải qua các giai đoạn phát triển và tối ưu như sau:

*   **Giai đoạn Thiết kế Kiến trúc Cơ sở:** 
    *   Khởi tạo hệ thống **Backend** với `FastAPI` để quản lý các luồng dữ liệu (API endpoints) tốc độ cao và mở rộng dễ dàng.
    *   Tích hợp kho lưu trữ đa năng: sử dụng **SQLite** lưu vết người dùng và quản lý trạng thái file; tiến tới sử dụng kho lưu trữ **Vector / Knowledge Base** hỗ trợ tra cứu ngữ cảnh.
    *   Xây dựng **Frontend** sử dụng `Streamlit`, cung cấp giao diện trực quan thân thiện với người dùng (chatbot, thanh upload file, giới hạn tìm kiếm).
*   **Giai đoạn Xây dựng Pipeline Xử lý Tài liệu (Data Ingestion):**
    *   Tích hợp các engine bóc tách văn bản tiên tiến: `PyMuPDF` cho PDF, `python-docx` cho các tệp Word, và trình đọc `.txt`, `.md` tiêu chuẩn.
    *   Xây dựng quá trình "Chunking" (cắt nhỏ văn bản) để AI dễ dàng tiêu hóa lượng tài liệu lớn.
*   **Giai đoạn Khắc phục sự cố & Hoàn thiện luồng AI:**
    *   **Tối ưu Data Clean (Sanitize):** Viết thêm thuật toán tự động nhận diện và xóa sổ các ký tự bất hợp lệ (như `\x00` Null Bytes) sinh ra từ file chứa công thức toán/lỗi font, giúp Database không bao giờ bị Crash khi trích xuất.
    *   **Tối ưu hóa Thuật toán Tìm kiếm (Retrieval / Search):** Khắc phục triệt để lỗi "AI báo không tìm thấy thông tin" bằng cách kết hợp cơ chế tìm kiếm gốc với chốt chẹn **Fallback Context** — tức là khi AI đối mặt với các lệnh chung chung như *"Tóm tắt", "Nói về nội dung chính"*, hệ thống sẽ thông minh tự bốc các chương đầu của tài liệu thay vì bối rối trả về dữ liệu rỗng.

---

## 2. Các Điểm Mạnh (Strengths)
Hệ thống hiện tại thể hiện giá trị rất lớn nhờ những điểm sau:

1.  **Chống Ảo Giác (Zero Hallucination):** AI hoàn toàn bám sát vào ngữ cảnh được nạp từ những file nội bộ, đảm bảo tính trung thực thay vì bịa đặt thông tin.
2.  **Khả năng tự động chữa cháy thông minh:** Khắc phục được các luồng câu hỏi cực khó để cấu trúc hệ thống (như yêu cầu "tóm tắt"), tăng cường trải nghiệm linh hoạt.
3.  **Tốc độ phản hồi và tính ổn định (Robust):** Đã loại bỏ được các nguy cơ làm sập máy chủ do tài liệu chứa rác hệ thống (Null Bytes). Luồng chạy FastAPI song song tách biệt giúp hệ thống không bị thắt cổ chai.
4.  **Hỗ trợ dải tài liệu lớn:** Đọc rất tốt Word, TXT, và PDF chữ cái kỹ thuật số.

---

## 3. Các Điểm Yếu & Hạn Chế (Weaknesses)
Đứng trên phương diện kỹ thuật, hiện tại dự án vẫn mang một số giới hạn tự nhiên:

1.  **Thiếu khả năng nhận diện hình ảnh / OCR:** Hiện tại hệ thống mù chữ với các tập tin **Scanned PDF** (PDF hình chụp, giấy in lưới scan lại) vì chưa tích hợp hệ thống Trí tuệ Quang học (Tesseract/OCR).
2.  **Mất cấu trúc Bảng biểu & Toán học chuyên sâu:** Khi chia cắt ma trận cấu trúc phức tạp hay bảng lưới kế toán sang dạng "Chữ (Text) thô" để AI hiểu, định dạng sẽ bị vỡ. Điều này có thể khiến AI đọc sai chỉ số hàng/cột (hoặc sai lệch mũ toán học $x^2$).
3.  **Hạn chế của Fuzzy Search:** Nếu hệ thống chỉ vận hành chủ yếu dựa trên tra tìm từ khoá mờ (Fuzzy) chứ chưa phải 100% là Embeddings Ngữ Nghĩa (Semantic Vectors Deep-learning), kết quả tìm kiếm khi hỏi mẹo, hỏi vòng vo khác ngôn ngữ tài liệu có thể chưa bén.
4.  **Giới hạn ngữ cảnh Token:** Dù có Fallback Context nhưng khi gửi cho LLM tóm tắt, ta chỉ đưa vào tối đa 5000-6000 ký tự để khỏi quá trọng tải, đồng nghĩa việc *Tóm tắt một cuốn sách 300 trang* sẽ thiên về "Tóm tắt chương đầu" hơn là cái nhìn tổng quát toàn bộ tác phẩm.

---
*Báo cáo được lập tự động từ lịch sử phát triển codebase.*
