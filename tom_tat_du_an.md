# Tóm Tắt Dự Án: Hệ Thống Đọc Tài Liệu Thông Minh (Smart Document Reader)

## Tổng Quan Dự Án

Dự án **Smart Document Reader** là một hệ thống đọc tài liệu thông minh sử dụng kiến trúc **RAG (Retrieval-Augmented Generation)**. Hệ thống cho phép người dùng upload tài liệu, đọc nội dung, tóm tắt bằng AI, và hỏi đáp thông minh dựa trên nội dung tài liệu.

**Phiên bản:** 2.0.0  
**Sinh viên thực hiện:** Lê Nhật Huy (B23DCAT126) | Phạm Hải Đông (B23DCVT090)  
**Công nghệ chính:** FastAPI + ChromaDB + CodexOAuth (GPT-5) + Streamlit

## Kiến Trúc Hệ Thống

### Backend (FastAPI)
- **Ngôn ngữ:** Python
- **Framework:** FastAPI
- **Database:** SQLite (cho metadata tài liệu và lịch sử chat)
- **Vector Database:** ChromaDB (cho lưu trữ và tìm kiếm vector embeddings)
- **AI Service:** CodexOAuth (GPT-5) cho generation và summarization
- **File Storage:** Local filesystem với extracted text files

### Frontend (Streamlit)
- **Framework:** Streamlit
- **UI Theme:** Dark theme với glassmorphism effects
- **Responsive:** Layout wide với sidebar thống kê

### Cấu Trúc Thư Mục
```
rag_project/
├── backend/           # FastAPI backend
│   ├── main.py        # App khởi tạo và lifecycle
│   ├── api/routes.py  # REST API endpoints
│   ├── core/config.py # Cấu hình hệ thống
│   ├── db/database.py # SQLite setup
│   ├── models/        # Pydantic schemas và domain models
│   ├── repositories/  # Data access layer
│   ├── services/      # Business logic (RAG, LLM, Document)
│   └── uploads/       # File storage
├── frontend/          # Streamlit UI
│   └── app.py         # Main UI application
├── chroma_db/         # Vector database storage
└── requirements.txt   # Python dependencies
```

## Workflow Chính

### 1. Upload và Xử Lý Tài Liệu
1. **Upload File:** Người dùng upload file (PDF, DOCX, TXT, MD) qua Streamlit UI
2. **Lưu File:** File được lưu vào thư mục `uploads/`
3. **Extract Text:** Nội dung được extract và lưu thành file `.extracted.txt`
4. **Chunking & Embedding:** Văn bản được chia thành chunks và tạo vector embeddings
5. **Index vào ChromaDB:** Embeddings được lưu vào vector database để tìm kiếm

### 2. Đọc và Quản Lý Tài Liệu
- **Xem Danh Sách:** Hiển thị tất cả tài liệu đã upload với trạng thái
- **Đọc Nội Dung:** Hiển thị nội dung đầy đủ của tài liệu
- **Download:** Cho phép tải file gốc hoặc file text đã extract
- **Xóa Tài Liệu:** Xóa file và dữ liệu liên quan

### 3. Tóm Tắt Tài Liệu (AI Summarization)
1. **Lấy Nội Dung:** Đọc nội dung tài liệu từ database
2. **Gọi AI:** Gửi nội dung cho CodexOAuth với prompt tóm tắt
3. **Cache Kết Quả:** Lưu tóm tắt vào database để tái sử dụng
4. **Trả Về:** Hiển thị tóm tắt cho người dùng

### 4. Hỏi Đáp Thông Minh (RAG Q&A)
1. **Nhận Câu Hỏi:** Người dùng nhập câu hỏi
2. **Retrieval:** Tìm kiếm top-k chunks liên quan nhất trong ChromaDB
3. **Generation:** Gửi chunks và câu hỏi cho CodexOAuth để sinh câu trả lời
4. **Lưu Lịch Sử:** Lưu câu hỏi, trả lời và sources vào database
5. **Trả Kết Quả:** Hiển thị câu trả lời với danh sách tài liệu nguồn

### 5. Tạo Bài Tập
- **Chọn Tài Liệu:** Chọn tài liệu để tạo bài tập
- **Chọn Loại:** Multiple choice, true/false, short answer, etc.
- **Gọi AI:** CodexOAuth tạo bài tập dựa trên nội dung
- **Hiển Thị:** Hiển thị bài tập với đáp án

### 6. Lịch Sử Chat
- **Xem Lịch Sử:** Danh sách tất cả phiên hỏi đáp
- **Chi Tiết:** Xem câu hỏi, trả lời và tài liệu nguồn
- **Xóa Lịch Sử:** Xóa toàn bộ hoặc từng phiên

## Nghiệp Vụ Chính

### Quản Lý Tài Liệu
- **Upload:** Hỗ trợ PDF, DOCX, TXT, MD (tối đa 50MB)
- **Xử Lý:** Background processing với status tracking
- **Metadata:** Lưu tên file, kích thước, loại, trạng thái, số chunks
- **Lifecycle:** Upload → Processing → Indexed/Error

### Tìm Kiếm và Truy Xuất
- **Vector Search:** Sử dụng ChromaDB cho semantic search
- **Relevance Scoring:** Điểm số độ liên quan cho mỗi chunk
- **Top-K Retrieval:** Lấy k chunks liên quan nhất
- **Source Tracking:** Theo dõi tài liệu nguồn cho mỗi câu trả lời

### AI Integration
- **CodexOAuth:** Sử dụng GPT-5 cho tất cả tác vụ AI
- **Prompt Engineering:** System prompts cho summarization, Q&A, exercise generation
- **Reasoning Effort:** Điều chỉnh effort cho các tác vụ khác nhau
- **Health Check:** Kiểm tra kết nối AI service

### Giao Diện Người Dùng
- **Multi-Tab UI:** Tabs cho từng chức năng chính
- **Real-time Status:** Hiển thị trạng thái processing và thống kê
- **Responsive Design:** Dark theme với animations
- **Error Handling:** Thông báo lỗi rõ ràng cho người dùng

## Chức Năng Chi Tiết

### API Endpoints (Backend)
- `POST /documents/upload` - Upload tài liệu
- `GET /documents` - Danh sách tài liệu
- `GET /documents/{id}/content` - Đọc nội dung
- `POST /documents/{id}/summarize` - Tóm tắt AI
- `POST /documents/{id}/exercise` - Tạo bài tập
- `DELETE /documents/{id}` - Xóa tài liệu
- `GET /documents/{id}/download` - Tải file
- `POST /chat/ask` - Hỏi đáp RAG
- `GET /chat/history` - Lịch sử chat
- `DELETE /chat/history` - Xóa lịch sử
- `GET /health` - Kiểm tra hệ thống

### Services (Business Logic)
- **DocumentService:** Xử lý upload, extract text, chunking
- **RAGService:** Điều phối retrieval và generation
- **LLMService:** Interface với CodexOAuth và ChromaDB
- **Repositories:** Data access cho documents và chat history

### Models và Schemas
- **Document:** Metadata tài liệu (id, name, size, type, status)
- **ChatHistory:** Lưu trữ Q&A sessions
- **Pydantic Schemas:** Validation cho API requests/responses

## Công Nghệ và Dependencies

### Python Packages
- **fastapi:** Web framework cho backend
- **uvicorn:** ASGI server
- **streamlit:** Frontend framework
- **sqlalchemy:** ORM cho SQLite
- **chromadb:** Vector database
- **codexoauth:** AI service client
- **python-multipart:** File upload handling
- **pypdf2, python-docx:** Document parsing

### Infrastructure
- **Local Development:** SQLite + ChromaDB local
- **File Storage:** Local filesystem
- **Vector Search:** ChromaDB với cosine similarity
- **AI Backend:** CodexOAuth cloud service

## Quy Trình Phát Triển

### Setup và Chạy
1. **Cài Đặt Dependencies:** `pip install -r requirements.txt`
2. **Khởi Tạo DB:** Auto-create tables khi start
3. **Chạy Backend:** `uvicorn main:app --reload`
4. **Chạy Frontend:** `streamlit run frontend/app.py`
5. **Truy Cập:** http://localhost:8501

### Testing
- **Health Check:** `/api/v1/health` kiểm tra kết nối
- **Manual Testing:** Upload file và test Q&A
- **Integration:** Test end-to-end workflow

## Điểm Mạnh và Tính Năng

### Technical Highlights
- **RAG Architecture:** Kết hợp retrieval và generation hiệu quả
- **Vector Search:** Semantic search với relevance scoring
- **Background Processing:** Non-blocking document indexing
- **Caching:** Summary caching để tối ưu performance
- **Error Handling:** Comprehensive error handling và logging

### User Experience
- **Intuitive UI:** Dark theme với glassmorphism
- **Real-time Feedback:** Status updates và progress indicators
- **Multi-format Support:** Hỗ trợ nhiều loại tài liệu
- **History Tracking:** Lưu trữ và xem lịch sử tương tác

### Educational Value
- **AI Integration:** Sử dụng state-of-the-art AI models
- **Modular Design:** Clean architecture với separation of concerns
- **Production Ready:** Error handling, logging, health checks

## Các Tính Năng Đã Cải Thiện & Hoàn Thiện (Báo Cáo Lần 2 so với Lần 1)

Trong quá trình phát triển giai đoạn tiếp theo của dự án, hệ thống đã được khắc phục triệt để các lỗi kỹ thuật và bổ sung thêm các nghiệp vụ quan trọng nhằm nang cao tính ổn định và tính bảo mật của hệ thống:

### 1. Khắc Phục Lỗi Streaming & API RAG
- **Sửa Lỗi Tương Tác Streaming:** Giải quyết dứt điểm lỗi `Attempted to access streaming response content, without having called read()` ở backend bằng cách cấu hình chuẩn chế độ `stream=False` khi giao tiếp API với mô hình LLM (CodexOAuth), đảm bảo dữ liệu trả về mượt mà hơn.
- **Sửa Lỗi Khởi Tạo Vector Database:** Khắc phục tình trạng trả về `500 Internal Server Error` và các lỗi `NoneType` khi khởi tạo `LocalRAG` hay lúc đếm số lượng chunk (`count`) trong ChromaDB, giúp quá trình nhúng (embedding) và tìm kiếm (retrieval) hoạt động ổn định.

### 2. Nâng Cấp Quản Lý Tài Liệu (Document Management)
- **Cơ Chế Sanitize Text:** Bổ sung việc loại bỏ, chuẩn hoá các ký tự đặc biệt hay mã hoá lỗi từ PDF/DOCX trước khi index, khắc phục hoàn toàn lỗi khi mã hóa (encoding) tài liệu chứa ký tự lạ.
- **Lựa Chọn & Tái Sử Dụng Document (Existing Files):** Cải tiến UX giúp người dùng dễ dàng chọn, trích xuất hay tham vấn các files đã upload thành công từ trước mà không cần tải lại file nhiều lần, tối ưu hoá thời gian xử lý.

### 3. Nâng Cấp Bảo Mật & Xác Thực
- **Luồng Đăng Nhập Mới (Browser Login):** Triển khai thêm thành phần Xác thực người dùng bằng trình duyệt (`browser_login.py`), hỗ trợ OAuth và quản lý phiên đăng nhập một cách bảo mật hơn, độc lập so với việc chỉ dùng API Key từ biến môi trường.
- **Ổn Định Định Danh API:** Refactor lại cách hệ thống `llm_service.py` phát hiện thư mục và nạp token Certificate (`CODEX_AUTH_FILE`), giúp dự án không bị văng lỗi (crash) khi xác thực quyền truy cập với AI Service.

## Kết Luận

Dự án Smart Document Reader trong Báo cáo Lần 2 đã trưởng thành hơn rất nhiều với độ ổn định cao. Những tính năng được cải thiện không chỉ giải quyết toàn bộ các bug nghiêm trọng (crash API, lỗi streaming, lỗi đọc file special characters) từ Lần 1 mà còn mang lại sự trơn tru trong tương tác với AI và quản trị file. Hệ thống đã tiến thêm một bước dài tới trạng thái Production-ready hoàn chỉnh.