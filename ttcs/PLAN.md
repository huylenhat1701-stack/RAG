# Quy trình hoạt động của hệ thống RAG

Hệ thống RAG (Retrieval-Augmented Generation) của bạn bao gồm 2 giai đoạn chính: **Nạp dữ liệu (Ingestion)** và **Hỏi đáp (Retrieval & Generation)**.

## Sơ đồ tổng quan

```mermaid
sequenceDiagram
    participant User as Người dùng
    participant FE as Streamlit (Frontend)
    participant BE as FastAPI (Backend)
    participant LC as LangChain (Pipeline)
    participant LLM as AI Model
    participant DB as Vector DB (Chroma)

    Note over User, DB: GIAI ĐOẠN 1: Nạp tài liệu (Data Ingestion)
    User->>FE: 1. Tải lên tài liệu (PDF, Word, TXT)
    FE->>BE: 2. Gửi file qua API
    BE->>LC: 3. Đọc nội dung & cắt thành các đoạn nhỏ (Chunks)
    LC->>LLM: 4. Chuyển đoạn chữ thành mảng số (Embedding)
    LLM-->>LC: 5. Trả về Vector Embeddings
    LC->>DB: 6. Lưu mảng số này cùng thông tin metadata
    DB-->>LC: 7. Xác nhận đã lưu
    LC-->>BE: 8. Hoàn tất quá trình nạp
    BE-->>FE: 9. Trả kết quả thành công
    FE-->>User: 10. Thông báo "Đã tải siêu văn bản"

    Note over User, DB: GIAI ĐOẠN 2: Truy vấn & Trả lời (Retrieval & Generation)
    User->>FE: 11. Nhập câu hỏi (Prompt)
    FE->>BE: 12. Gửi câu hỏi qua API
    BE->>LC: 13. Xử lý câu hỏi
    LC->>LLM: 14. Chuyển câu hỏi vừa nhận thành mảng số (Vector)
    LLM-->>LC: 15. Trả về Vector câu hỏi
    LC->>DB: 16. Tìm kiếm ngữ nghĩa (Semantic Search)
    DB-->>LC: 17. Trả về Top K đoạn tài liệu gốc phù hợp nhất (Context)
    LC->>LLM: 18. Gửi AI: "Dựa vào ngữ cảnh này (Context), hãy trả lời Câu hỏi"
    LLM-->>LC: 19. Trả lời bằng ngôn ngữ tự nhiên
    LC-->>BE: 20. Trả lời cuối cùng
    BE-->>FE: 21. Đẩy câu trả lời cho UI
    FE-->>User: 22. Hiển thị thông điệp lên màn hình Chat
```

## Giải thích chi tiết các bước

### Giai đoạn 1: Nạp tài liệu vào bộ nhớ AI (Data Ingestion)

Khi người dùng upload một cuốn sách hoặc tài liệu lên, hệ thống sẽ thực hiện theo trình tự sau:
1. **Trích xuất & Cắt nhỏ (Chunking):** Tài liệu sẽ được LangChain trích xuất văn bản chữ và chia nhỏ (chunk) thành hàng nghìn đoạn ngắn khoảng 500-1000 từ để đảm bảo giới hạn phân tích của AI.
2. **Vector hóa (Embedding):** Mỗi đoạn chữ sẽ được đi qua mô hình nhúng (Embedding Model) để chuyển đổi sang các dãy số tọa độ liên tục. Máy tính tính toán khoảng cách dãy số sẽ nhanh hơn chữ viết.
3. **Lưu trữ (ChromaDB):** Toàn bộ các dòng tọa độ dãy số đó sẽ được cất vào trong một bộ nhớ được tối ưu cho RAG gọi là Vector Database (trong trường hợp dự án này là ChromaDB). Đi kèm với nó là các Metadata như (tên tác giả, thông tin bổ sung).

### Giai đoạn 2: Lấy thông tin và trả lời người dùng (Retrieval & Generation)

Khi người dùng đặt câu hỏi trên giao diện Streamlit:
1. **Tìm kiếm (Semantic Search):** Hệ thống lấy câu hỏi vừa nhập và tiếp tục biến nó thành một dải số Vector. Sau đó nó vào ChromaDB để rà soát xem **mảng văn bản nào gần với chỉ số của câu hỏi nhất**. Nó sẽ nhặt ra khoảng 3-5 đoạn văn bản liên quan nhất (Top K).
2. **Sinh câu trả lời (Generation):** Hệ thống gom 3-5 đoạn đó cộng với câu hỏi gốc đặt ra, nhét chung vào một cái hộp tên là Prompt. Prompt này được gửi đến AI LLM (như OpenAI ChatGPT hoặc Gemini) yêu cầu phản hồi câu trả lời sử dụng thông tin và sự thật từ những "Ngữ cảnh" vừa được cung cấp từ ChromaDB. Việc này đảm bảo AI không sinh ra câu trả lời ảo (Hallucination).
3. Kết quả phản hồi (Chatbot) sẽ được đẩy xuống trở lại giao diện API (FastAPI) vào Frontend (Streamlit) để phục vụ cho người dùng đọc và tìm kiếm.
