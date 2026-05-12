# Kịch Bản Thuyết Trình Demo Dự Án RAG - Smart Document Reader

## Lời Mở Đầu (1-2 phút)
- **Chào hỏi:** Xin chào thầy cô và các bạn. Hôm nay, nhóm chúng em (Lê Nhật Huy và Phạm Hải Đông) xin trình bày demo "Hệ thống Đọc Tài Liệu Thông Minh" ứng dụng công nghệ RAG.
- **Mục tiêu:** Hệ thống giúp giải quyết vấn đề đọc, tra cứu và tổng hợp thông tin từ các tài liệu dài một cách nhanh chóng và chính xác.
- **Công nghệ chính:** Frontend dùng Streamlit, Backend dùng FastAPI, lưu trữ dữ liệu bằng SQLite & ChromaDB, và sử dụng Local LLM.

---

## Tính năng 1: Quản lý và Xử lý Tài Liệu (2 phút)
- **Hành động trên UI:** Mở tab "Quản Lý Tài Liệu". Upload một file PDF/DOCX.
- **Thuyết trình luồng xử lý:**
  1. Khi người dùng tải file lên, hệ thống sẽ lưu file vật lý và tạo một bản ghi với trạng thái `UPLOADED` trong database (SQLite).
  2. Ngay sau đó, một tiến trình chạy ngầm (background task) được kích hoạt và trạng thái chuyển sang `INDEXING`.
  3. Hệ thống sẽ bóc tách văn bản (Text Extraction) từ file PDF/DOCX, làm sạch dữ liệu (loại bỏ ký tự lỗi) và chia nhỏ văn bản (Chunking) thành các đoạn khoảng 600 từ.
  4. Các đoạn này được đưa qua mô hình Embedding để biến thành vector số học và lưu vào ChromaDB.
  5. Cuối cùng, trạng thái cập nhật thành `INDEXED`, sẵn sàng cho các chức năng AI và tìm kiếm.

---

## Tính năng 2: Đọc Nội Dung Tài Liệu (1 phút)
- **Hành động trên UI:** Mở tab "Đọc Tài Liệu", chọn tài liệu vừa upload.
- **Thuyết trình luồng xử lý:**
  1. Hệ thống cung cấp khả năng xem trước toàn bộ nội dung văn bản đã được bóc tách ngay trên web.
  2. Ở bước này, để đảm bảo tốc độ và tính ổn định, hệ thống ưu tiên đọc từ file text tạm (`.extracted.txt`) đã được chuẩn hóa trong quá trình xử lý, giúp người dùng không cần tải lại file PDF nặng nề.

---

## Tính năng 3: Tóm Tắt Tài Liệu Bằng AI (2 phút)
- **Hành động trên UI:** Mở tab "Tóm Tắt", chọn tài liệu và nhấn nút "Tóm tắt tài liệu".
- **Thuyết trình luồng xử lý:**
  1. Nhóm thiết kế thuật toán linh hoạt để giải quyết bài toán giới hạn bộ nhớ của Local LLM (Context Window).
  2. **Nếu tài liệu ngắn:** Hệ thống đưa toàn bộ nội dung vào Prompt để AI đọc và tóm tắt 1 lần.
  3. **Nếu tài liệu quá dài:** Hệ thống tự động chia văn bản thành các phân đoạn nhỏ, cho AI tóm tắt từng phần, sau đó dùng AI một lần nữa để tổng hợp các tóm tắt con thành một bài viết hoàn chỉnh.
  4. Đặc biệt, kết quả tóm tắt sẽ được lưu (cache) lại vào Database. Ở những lần xem sau, kết quả sẽ hiện ra ngay lập tức mà không cần gọi lại AI.

---

## Tính năng 4: Hỏi Đáp Thông Minh (RAG) (3-4 phút)
- **Hành động trên UI:** Mở tab "Hỏi & Đáp". Chọn 1 tài liệu hoặc để chế độ tìm trên tất cả tài liệu. Đặt một câu hỏi.
- **Thuyết trình luồng xử lý:**
  Đây là tính năng cốt lõi. Hệ thống có khả năng tự động phân tích độ lớn của dữ liệu để chọn thuật toán tối ưu nhất:
  1. **Chế độ Full-Context Mode:** Khi người dùng chọn 1 tài liệu có nội dung ngắn, hệ thống sẽ gom toàn bộ văn bản đưa vào Prompt. Chế độ này giúp AI có cái nhìn toàn cảnh 100% và trả lời chính xác, không bị sót thông tin.
  2. **Chế độ RAG Mode:** Nếu nội dung quá dài hoặc người dùng muốn tìm kiếm trên tất cả tài liệu:
     - Câu hỏi sẽ được nhúng (embed) thành vector.
     - Hệ thống quét qua ChromaDB để lấy ra top K đoạn văn bản (chunks) liên quan nhất.
     - Ghép các chunk này thành ngữ cảnh (context) đưa cho AI để sinh câu trả lời.
  3. Dù ở chế độ nào, hệ thống luôn minh bạch hiển thị **Nguồn trích dẫn** để người dùng dễ dàng kiểm chứng lại độ tin cậy của câu trả lời.

---

## Tính năng 5: Sinh Bài Tập & Trắc Nghiệm (2 phút)
- **Hành động trên UI:** Mở tab "Bài Tập / Quiz". Chọn tài liệu, chọn số lượng câu hỏi và bắt đầu tạo.
- **Thuyết trình luồng xử lý:**
  1. Tính năng này giúp biến tài liệu thành các bài kiểm tra tương tác.
  2. Đối với chế độ sinh trắc nghiệm, thuật toán của nhóm có cơ chế xử lý rất đặc biệt: Do các mô hình AI nhỏ ở local thường dễ bị loạn và trả về sai định dạng JSON, hệ thống sẽ yêu cầu AI tạo từng đợt nhỏ (batch: 3 câu/lần).
  3. Sau đó, hệ thống sẽ thử parse JSON. Nếu AI trả về text thô (không chuẩn JSON), hệ thống có sẵn các hàm "fallback parsing" dùng Regex để tự động trích xuất các mẫu "Câu 1:", "A.", "B.", "Đáp án:" từ text thường.
  4. Nhờ vậy, dữ liệu vẫn được cấu trúc hóa thành công và hiển thị giao diện thi trắc nghiệm (Quiz) tương tác mượt mà cho người dùng.

---

## Tổng kết (1 phút)
- **Hành động:** Quay lại trang chủ hoặc mở tab Lịch sử để show lại quá trình tương tác.
- **Tóm lược:** Hệ thống đã kết hợp thành công giữa đọc toàn văn và tìm kiếm vector (RAG), xử lý được các hạn chế của Local LLM như giới hạn độ dài context và lỗi định dạng. Dự án mang tính ứng dụng thực tiễn cao cho việc học tập và nghiên cứu.
- Cảm ơn thầy cô và các bạn đã lắng nghe. Nhóm xin phép chuyển sang phần giải đáp câu hỏi (Q&A).
