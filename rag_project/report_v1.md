### 1. Mục 1.4.1 Luồng xử lý chính (Chương I)
**Hành động:** Thay thế toàn bộ phần mô tả Luồng Upload và Luồng Hỏi-Đáp để bổ sung chi tiết kỹ thuật về làm sạch NULL byte, Context-aware Mode Selection và công thức tính Confidence Score.

**Nội dung thay thế:**
> **Luồng Upload Tài liệu:** Upload File → Lưu vật lý → Trả Response ngay → Extract Text (background) → **Làm sạch NULL bytes (loại bỏ triệt để `\x00`, `\u0000` để tránh lỗi ghi SQLite và hỏng index ChromaDB)** → Sliding Window Chunking **dựa trên word-level** (600 từ, overlap 80; step 520 từ) → Embedding theo E5 Prefix Strategy (**bắt buộc thêm prefix `"passage: "`**) → Index vào ChromaDB → Cập nhật trạng thái INDEXED.
> 
> **Luồng Hỏi-Đáp:** Câu hỏi người dùng → Nhúng truy vấn theo E5 Prefix Strategy (**thêm prefix `"query: "`**) → **Context-aware Mode Selection (tự động chọn Full-Context Mode nếu tổng văn bản nằm trong giới hạn an toàn của context window, hoặc RAG Mode nếu vượt ngưỡng)** → Vector Search → Tính Cosine Similarity **($s = \max(0.0, 1.0 - d)$)** → Dual-Threshold Fallback **với các ngưỡng chuẩn hóa (`NO_CONTEXT_THRESHOLD = 0.4`, `RELEVANCE_THRESHOLD = 0.5`)**: max score < 0.4 thì từ chối gọi LLM; từ 0.4 đến dưới 0.5 thì dùng toàn bộ chunks truy xuất được làm fallback an toàn; từ 0.5 trở lên thì chỉ lọc các chunk đạt ngưỡng → LLM sinh câu trả lời → Smart Sentence Splitting → NLI Verification → Trả kết quả, nguồn trích dẫn, điểm tin cậy **(tính bằng trung bình có trọng số $\Sigma(s_i^2) / \Sigma(s_i)$)** và cảnh báo nếu có.

---

### 2. Mục 2.2.2 Chunking Strategy (Chương II)
**Hành động:** Mở rộng đoạn văn để giải thích lý do sử dụng word-level và bổ sung bước phòng vệ NULL-byte (từ A.2 và A.10).

**Nội dung thay thế:**
> Chunking là bước phân chia tài liệu thành các đoạn nhỏ. Trước khi chia, hệ thống thực hiện bước phòng vệ quan trọng ở tầng tiền xử lý: loại bỏ triệt để ký tự NULL (`text.replace('\x00', '')` và `text.replace('\u0000', '')`) nhằm tránh lỗi cú pháp SQLite và hỏng thao tác ghi dữ liệu trong ChromaDB do chuỗi chứa NUL gây ra.
> Chiến lược được chọn là Sliding Window Chunking ở mức **word-level** thay vì character-level: chunk size 600 từ, overlap 80 từ và bước nhảy Step = 520 từ. Việc chia theo từ giúp hạn chế tối đa việc cắt gãy từ/cụm từ tiếng Việt, đồng thời giữ lại 80 từ trùng lặp để bảo toàn mạch ngữ cảnh chuyển tiếp giữa hai phân đoạn liên tiếp.

---

### 3. Mục 2.2.3 Embedding Model — multilingual-e5-small (Chương II)
**Hành động:** Bổ sung yêu cầu Prefix của E5, công thức chuyển đổi khoảng cách Cosine và chiến lược Search Cache đa luồng (từ A.3).

**Nội dung thay thế:**
> Mô hình intfloat/multilingual-e5-small [Wang et al., 2024] được chọn vì hiệu năng tốt trên 100+ ngôn ngữ. 
> **Yêu cầu Prefix:** E5 được huấn luyện phân biệt nhiệm vụ passage-query theo tiền tố. Do đó, khi index tài liệu, hệ thống bắt buộc nối chuỗi `"passage: " + Text`; khi tìm kiếm, nối chuỗi `"query: " + Query`.
> **Khoảng cách Cosine:** ChromaDB được cấu hình theo Cosine Distance. Khoảng cách $d$ được đổi thành điểm tương đồng $s$ theo công thức $s = \max(0.0, 1.0 - d)$.
> **Search Cache:** Để giảm chi phí tính toán, hệ thống triển khai search cache an toàn đa luồng sử dụng `threading.Lock()`. Khóa cache được băm MD5 từ query, top_k và danh sách allowed files (đã sắp xếp). Cache giới hạn 256 mục, TTL 3600 giây và tự động invalidate khi có tài liệu mới nạp vào ChromaDB.

---

### 4. Mục 2.2.6 Relevance Scoring và Thresholding (Chương II)
**Hành động:** Chuẩn hóa tên các ngưỡng (Threshold) và làm rõ cơ chế Context-aware Mode Selection (từ A.4).

**Nội dung thay thế:**
> **Context-aware Mode Selection:** Hệ thống tự động chọn giữa Full-Context Mode và RAG Mode dựa trên giới hạn an toàn của context window thay vì một con số ký tự cố định, đảm bảo recall tối đa khi tài liệu ngắn.
> **Dual-Threshold Fallback Strategy:** Hệ thống áp dụng bộ lọc hai ngưỡng chuẩn hóa:
> - `NO_CONTEXT_THRESHOLD = 0.4`: Nếu mọi chunk có similarity < 0.4, hệ thống không gọi LLM và trả về thông báo không tìm thấy thông tin (chống hallucination sớm).
> - `RELEVANCE_THRESHOLD = 0.5`: Nếu có chunk đạt $\ge 0.5$, chỉ các chunk đạt ngưỡng này được đưa vào context.
> - *Vùng Fallback an toàn [0.4, 0.5):* Nếu có chunk đạt 0.4 nhưng chưa có chunk nào đạt 0.5, hệ thống dùng toàn bộ chunks truy xuất được làm fallback thay vì gửi context rỗng.
> **Confidence Score:** Điểm tin cậy được tính bằng trung bình có trọng số: $Confidence = \Sigma(s_i^2) / \Sigma(s_i)$. Việc bình phương similarity khiến các chunk có độ liên quan cao đóng góp mạnh hơn, phản ánh trực giác rằng câu trả lời dựa trên bằng chứng sát câu hỏi cần được đánh giá đáng tin cậy hơn.

---

### 5. Mục 2.3.3 Công Thức Cập Nhật BKT & 2.3.4 Ứng dụng (Chương II)
**Hành động:** Thêm ghi chú chuẩn hóa $P(L_0)$, các công thức Bayesian Update và định nghĩa "weak chunks" (từ A.6).

**Nội dung thay thế:**
> **2.3.3 Công Thức Cập Nhật BKT**
> *Lưu ý chuẩn hóa:* Giá trị $P(L_0)$ được thống nhất chuẩn hóa về 0.5 (thay vì 0.3 như một số tài liệu gốc) để đồng bộ với báo cáo thuật toán.
> Gọi $L_k \in \{0, 1\}$ là trạng thái ẩn (chưa hiểu / đã hiểu) của knowledge component (chunk) thứ $k$. Sau mỗi lần trả lời, xác suất tri thức được cập nhật:
> - **Khi trả lời đúng ($C_k = 1$):** 
> $$P(L_k | C_k = 1) = \frac{P(L_k)(1 - p_{slip})}{P(L_k)(1 - p_{slip}) + (1 - P(L_k))p_{guess}}$$
> - **Khi trả lời sai ($C_k = 0$):** 
> $$P(L_k | C_k = 0) = \frac{P(L_k)p_{slip}}{P(L_k)p_{slip} + (1 - P(L_k))(1 - p_{guess})}$$
> - **Cập nhật chuyển trạng thái (Transition):** 
> $$P(L_{new}) = P(L_k | C_k) + (1 - P(L_k | C_k))p_{transit}$$
> 
> **2.3.4 Ứng dụng BKT vào Hệ thống**
> Trong Smart Document Reader, BKT được áp dụng ở mức độ chunk. Các chunk có xác suất nắm vững $P(L_k) < 0.60$ được phân loại là **weak chunks** và được ưu tiên cho sinh câu hỏi ôn tập hoặc lập lộ trình học cá nhân hóa.

---

### 6. Mục 2.4 Natural Language Inference (NLI) và Kiểm Chứng (Chương II)
**Hành động:** Tách thành 2 mục nhỏ để đưa thuật toán Smart Sentence Splitting và Logic trừ điểm (Penalty) vào (từ A.5).

**Nội dung thay thế:**
> **2.4.1 Tách câu thông minh (Smart Sentence Splitting)**
> Trước khi đưa vào NLI, văn bản tiếng Việt cần được tách câu chính xác. Việc chia câu chỉ dựa trên dấu chấm/hỏi/chấm than dễ gây ngắt sai tại số thập phân, tên riêng viết tắt hoặc học hàm/học vị. Hệ thống áp dụng quy trình 4 bước: (1) Bảo vệ số thập phân, (2) Bảo vệ tên riêng viết tắt, (3) Bảo vệ từ viết tắt học thuật/danh xưng, (4) Chia câu và khôi phục ký tự đã bảo vệ.
> 
> **2.4.2 Bài toán NLI và Cơ chế Hậu kiểm (Post-verification)**
> NLI đối chiếu từng claim trong câu trả lời (hypothesis) với premise là ngữ cảnh gốc thông qua mô hình mDeBERTa-v3-base-xnli.
> **Cơ chế trừ điểm tin cậy (Penalty Logic):**
> - *Contradiction (Mâu thuẫn):* Trừ 0.2 điểm confidence và gắn cảnh báo.
> - *Neutral (Trung lập):* Trừ 0.1 điểm confidence.
> - *Entailment (Kéo theo):* Giữ nguyên điểm.
> Đây là lớp hàng rào logic hậu kiểm giúp phát hiện các câu trả lời vượt quá bằng chứng được cung cấp.

---

### 7. Mục 2.5 Sinh Câu Hỏi Trắc Nghiệm Tự Động (Chương II)
**Hành động:** Bổ sung Mixed Sampling Strategy, Bloom's Taxonomy và chi tiết 4 lớp Fallback Parser (từ A.7).

**Nội dung thay thế:**
> **2.5.1 Chiến lược Lấy mẫu Hỗ hợp & Bloom's Taxonomy**
> Để tránh hiện tượng *BKT lock-in* (chỉ tập trung vào điểm yếu), hệ thống áp dụng **Mixed Sampling Strategy**: tối đa 50% câu hỏi được lấy từ *weak chunks*, phần còn lại lấy ngẫu nhiên từ toàn bộ chunks. Thang nhận thức Bloom (Remember, Understand, Apply, Analyze) được tích hợp vào Chain-of-Thought prompt để đa dạng hóa mục tiêu kiểm tra.
> 
> **2.5.2 Micro-Batching và Multi-layer Fallback Parser**
> Do Gemma 3 4B là mô hình nhỏ, giải pháp Micro-batching (sinh 3 câu/lần) được áp dụng. Bộ **Multi-layer Fallback Parser** gồm 4 lớp phòng vệ: (1) Lọc preamble, (2) Parse JSON / double-loads JSON, (3) Regex fallback parsing, (4) Numbered list fallback. Chuỗi này đảm bảo hệ thống vẫn bóc tách được câu hỏi ngay cả khi LLM cục bộ trả về văn bản không hoàn toàn chuẩn JSON.

---

### 8. Mục 3.2.1 Chỉ số đánh giá (Chương III)
**Hành động:** Bổ sung các chỉ số đánh giá Retrieval chuyên sâu như Recall@K, Spearman Rank Correlation và Latency Profile (từ A.9).

**Nội dung thay thế:**
> Hệ thống đánh giá RAG dựa trên framework 3 tầng với các metrics cốt lõi:
> - **Answer Length & Multi-source Rate:** Đo độ dài và tính đa nguồn của câu trả lời.
> - **Confidence Score & Rejection Rate:** Đánh giá độ tin cậy và tỷ lệ từ chối trả lời của Dual-Threshold.
> - **Recall@K ($K \in \{3, 5, 15\}$):** Đo tỷ lệ các ground-truth chunks được truy xuất trong Top K ($Recall@K = |R_K \cap GT| / |GT|$). Đây là chỉ số cốt lõi đánh giá chất lượng retrieval trước khi sinh câu trả lời.
> - **Spearman Rank Correlation ($\rho$):** Đo độ đồng thuận thứ hạng giữa cosine similarity và khoảng cách L2 trong quá trình truy xuất ($\rho = 1 - \frac{6\Sigma d_i^2}{N(N^2 - 1)}$).
> - **Latency Profile:** Phân rã tổng thời gian theo các pha (Embedding, Vector Search, LLM Gen, NLI) để nhận diện bottleneck tầng.

---

### 9. Thêm mới Mục 2.7: Mô Hình Hóa Bản Đồ Tri Thức (Chương II)
**Hành động:** Thêm mục này vào cuối Chương II (trước mục 2.6 Kiến Trúc Phần Mềm) để tích hợp nội dung từ A.8.

**Nội dung thêm mới:**
> **2.7 Mô Hình Hóa Bản Đồ Tri Thức (Knowledge Graph)**
> Bản đồ tri thức được mô hình hóa như đồ thị vô hướng $G = (V, E)$, trong đó đỉnh $V$ là các chunks và cạnh $E$ biểu diễn mối liên hệ ngữ nghĩa. Để tránh quá tải trực quan, hệ thống lọc tối đa 50 chunks có mức hiểu BKT thấp nhất (*weak chunks*). Cạnh giữa hai chunk $i$ và $j$ được tạo khi $Sim(v_i, v_j) > 0.60$, với trọng số cạnh là điểm tương đồng cosine. Cấu trúc này giúp người học quan sát cụm kiến thức liên quan và nhận biết sự tương quan giữa các phần kiến thức.

---

### Hướng dẫn bổ sung:
1. **Bảng A.1 (Tổng hợp tham số):** Bạn có thể chuyển bảng này lên làm **Bảng 2.5: Tổng hợp tham số thuật toán cốt lõi** ở cuối Chương II để người đọc dễ theo dõi.
2. **Xóa Phụ lục A:** Sau khi copy các đoạn trên vào đúng vị trí, hãy xóa toàn bộ text từ chữ "PHỤ LỤC A..." đến hết tài liệu.
3. **Cập nhật Mục lục:** Xóa các dòng mục lục của Phụ lục A và thêm mục `2.7 Mô Hình Hóa Bản Đồ Tri Thức` vào Mục lục chi tiết.