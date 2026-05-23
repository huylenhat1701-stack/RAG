# Kế Hoạch Cải Thiện Thuật Toán Tạo Lộ Trình Học Tập (Cập nhật chi tiết hóa)

Vấn đề hiện tại của hệ thống không nằm ở việc cần "train" (huấn luyện) lại một mô hình AI mới, mà nằm ở **cách chúng ta thiết kế Prompt (Prompt Engineering)** và **cách cung cấp dữ liệu ngữ cảnh (Context)** cho AI. 

Để đảm bảo AI trả ra một lộ trình **cụ thể, rõ ràng và chi tiết** cho người học (không chỉ là những lời khuyên chung chung), chúng ta sẽ thiết kế một Prompt buộc AI phải tuân theo cấu trúc hành động.

## Proposed Changes

Chúng ta sẽ tối ưu thuật toán này bằng phương pháp **Context Enrichment** và **Structured Prompting**.

### backend/services/rag_service.py

#### [MODIFY] rag_service.py
* **Thay đổi hàm `generate_learning_path`**:
    * **Gộp Ngữ Cảnh (Aggregating Context)**: Gộp tất cả các đoạn nội dung yếu (snippets) thành một văn bản tổng hợp.
    * **Thêm BKT Score vào Context**: Đưa điểm xác suất hiểu bài (BKT probability) của từng chunk vào prompt để AI biết phần nào người dùng hổng nặng nhất (cần ưu tiên xử lý trước).
    * **Cấu trúc lại Prompt (Chain-of-Thought & Actionable)**: Gọi AI **1 lần duy nhất**. Yêu cầu AI không chỉ đưa ra lời khuyên, mà phải chia thành các **BƯỚC HÀNH ĐỘNG (Actionable Steps)** rõ ràng. Trả về kết quả dưới dạng **JSON Array**.

* **Ví dụ Prompt Mới Sẽ Dùng (Đã được chi tiết hóa cực độ)**:
  ```text
  Bạn là một chuyên gia giáo dục thiết kế lộ trình học tập cá nhân hóa. Dưới đây là các phần kiến thức mà người học đang yếu từ tài liệu '{doc.file_name}', kèm theo điểm số hiểu bài (BKT Score - càng thấp càng yếu):
  
  [Phần 1 - Điểm: 30%]: {snippet_1}
  [Phần 2 - Điểm: 50%]: {snippet_2}
  ...
  
  Nhiệm vụ của bạn là phân tích các lỗ hổng này và vạch ra một lộ trình ôn tập thật cụ thể, rõ ràng, hướng dẫn người học phải làm gì.
  Hãy sắp xếp theo thứ tự ưu tiên (phần yếu nhất hoặc nền tảng nhất học trước).
  
  Trả về kết quả dưới dạng JSON Array chính xác như sau:
  [
    {
      "topic": "Tên chủ đề ngắn gọn (ví dụ: Khái niệm OOP)",
      "advice": "Lời khuyên tổng quan và giải thích TẠI SAO phải ôn phần này. Liệt kê 2-3 HÀNH ĐỘNG CỤ THỂ (ví dụ: 1. Đọc lại định nghĩa X. 2. Tự lấy ví dụ về Y. 3. Phân biệt Z)."
    }
  ]
  ```

## Lợi Ích Của Cách Làm Này
1. **Tính Hành Động Cao (Actionable)**: Bằng cách ép AI phải viết ra "2-3 hành động cụ thể" trong mục `advice`, người học sẽ biết chính xác mình cần đọc lại đoạn nào, luyện tập cái gì thay vì chỉ đọc "hãy ôn lại kỹ hơn".
2. **Tiết kiệm chi phí/thời gian API**: Chỉ gọi AI 1 lần thay vì nhiều lần.
3. **Lộ trình logic hơn**: AI phân tích tổng thể để xếp hạng ưu tiên, tạo ra một roadmap từ dễ đến khó hoặc từ lỗ hổng nặng nhất đến nhẹ nhất.

## User Review Required
> [!IMPORTANT]
> Phương pháp này thay đổi cách gọi API (chuyển từ gọi nhiều lần lẻ tẻ sang 1 lần tổng hợp) và yêu cầu AI trả về JSON.
> Xin bạn xem xét kế hoạch cập nhật này. Nếu đồng ý, tôi sẽ tiến hành cập nhật code trực tiếp vào `rag_service.py`.
