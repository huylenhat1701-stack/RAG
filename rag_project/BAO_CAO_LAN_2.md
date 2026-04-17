# BÁO CÁO TIẾN ĐỘ LẦN 2
**Đề tài:** Xây dựng hệ thống hỏi đáp thông minh trên dữ liệu cục bộ sử dụng kiến trúc RAG (Retrieval-Augmented Generation)
**Sinh viên thực hiện:** 
- Lê Nhật Huy - B23DCAT126
- Phạm Hải Đông - B23DCVT090

---

## 1. TỔNG QUAN TIẾN ĐỘ
Tiếp nối các công việc nền tảng (Thiết kế kiến trúc, Database Schema, thiết lập môi trường) đã hoàn thành ở Báo cáo lần 1, nhóm đã tập trung triển khai kỹ thuật thực tế cho các Giai đoạn 2, 3 và 4. 
Tính đến thời điểm hiện tại, dự án đã cơ bản hoàn thiện toàn bộ luồng xử lý (Pipeline) của hệ thống RAG, từ giao diện người dùng (Frontend) đến xử lý nghiệp vụ AI (Backend) và Cơ sở dữ liệu.

## 2. KHỐI LƯỢNG CÔNG VIỆC ĐÃ HOÀN THÀNH (GIAI ĐOẠN 2, 3, 4)

### 2.1. Hoàn thiện Core Backend (FastAPI) & Data Ingestion
- **Xây dựng hệ thống API nội bộ:** Hoàn thành các RESTful API endpoints cốt lõi bao gồm tải tài liệu (`/upload`), truy vấn hỏi đáp (`/ask`), và lấy lịch sử (`/history`).
- **Trích xuất dữ liệu đa định dạng (Data Extraction):** Đã tích hợp thành công các thư viện `PyMuPDF` (cho file PDF) và `python-docx` (cho file Word). Hệ thống có khả năng bóc tách toàn bộ văn bản (text) với tốc độ cao.
- **Tối ưu hóa Data Sanitization:** Đối mặt với tình trạng file PDF chứa công thức toán học bị chèn các ký tự `Null Bytes` (`\x00`) gây lỗi cơ sở dữ liệu (SQLite `IntegrityError`), nhóm đã tự xây dựng một bộ lọc (Sanitizer) tự động dọn rác văn bản ngay sau khi trích xuất, đảm bảo luồng lưu trữ hoạt động mượt mà.

### 2.2. Tích hợp AI (LLM) & Cấu hình Lưu trữ Véc-tơ (Knowledge Base)
- **Cấu hình Local Knowledge Base:** Sử dụng cơ chế lưu trữ phân đoạn văn bản và truy xuất kết hợp (Semantic Search / Fuzzy Search) giúp hệ thống khoanh vùng được đoạn văn bản thô chứa thông tin liên quan tới câu hỏi.
- **Thực thi luồng RAG Service:** Khi API nhận câu hỏi, module `LLM Service` sẽ mã hóa câu hỏi, chủ động tính toán khoảng cách vector và trích xuất Top K tài liệu (chunks) phù hợp nhất làm Ngữ cảnh (Context) để đẩy vào Prompt của LLM.
- **Tính năng Fallback thông minh (Vượt trội):** Khắc phục nhược điểm của RAG khi người dùng đặt câu hỏi chung chung (VD: "Tóm tắt tài liệu này", "Nói về nội dung chính"). Thay vì báo lỗi "Không tìm thấy nội dung", hệ thống đã được lập trình để tự động kích hoạt **Fallback Context** (lấy các trang đầu tiên của tài liệu) để AI có cơ sở từ vựng trả lời trơn tru.

### 2.3. Xây dựng Frontend Application (Streamlit)
- **Giao diện tương tác trực tiếp:** Hoàn thiện UI với Streamlit, kết nối trực tiếp với các endpoint FastAPI.
- **Quản lý phiên hội thoại:** Hiển thị rõ ràng đoạn chat, lịch sử trả lời và phân tách rõ phần tài liệu tham khảo (Sources/Citations) để người dùng có thể kiểm chứng luồng suy luận của AI (Zero Hallucination).
- **Bộ lọc động (Dynamic Filtering):** Xây dựng khả năng cho phép người dùng tick chọn giới hạn tìm kiếm câu trả lời nằm trong một bộ cục bộ (VD: Chỉ tìm trong sách A, bỏ qua sách B).

## 3. KHÓ KHĂN ĐÃ GIẢI QUYẾT TRONG GIAI ĐOẠN NÀY

| Thách thức | Giải pháp thực tế áp dụng |
| :--- | :--- |
| Lỗi Crash DB do file PDF chứa ký tự lỗi (Toán học, Bảng biểu vỡ format). | Can thiệp trực tiếp vào hàm `extract_document_text`, dùng Regex và thuật toán Replace xóa bỏ toàn bộ `\x00` và Hexadecimal ẩn trước khi đẩy xuống DB. |
| AI báo lỗi "Không tìm thấy Context" với những câu lệnh Tóm tắt | Viết đè hàm truy vấn thuật toán tìm kiếm. Nếu mảng Context rỗng do điểm trùng khớp (score) thấp, hệ thống tự động chèn 5 đoạn văn bản đầu tiên của file làm Context mồi (Fallback). |

## 4. KẾ HOẠCH GIAI ĐOẠN CUỐI (TỐI ƯU & BÁO CÁO NGHIỆM THU)
Để chuẩn bị cho đợt bảo vệ cuối kỳ, nhóm sẽ thực hiện các công việc sau trong giai đoạn nước rút:
1. **Kiểm thử (Testing) với tập dữ liệu lớn:** Tải thực tế các sách văn bản dày > 300 trang để đo lường độ trễ (Latency) của API và tinh chỉnh tham số `chunk_size`.
2. **Gợi mở Hướng đi tương lai (Future Works):** Viết báo cáo thực tế hóa giới hạn chưa xử lý được (chưa có OCR cho ảnh Scan, chưa bóc tách HTML cấu trúc Bảng Biểu).
3. **Đóng gói mã nguồn & Viết Documents:** Đóng gói thư viện theo `requirements.txt` chuẩn, hướng dẫn chạy file `start.bat` để hội đồng nhà trường dễ dàng thao tác chạy thử nghiệm mà không vướng lỗi môi trường. Mài giũa kiến thức để bảo vệ đồ án nghiệm thu.
