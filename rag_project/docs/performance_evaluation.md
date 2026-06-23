# Đánh Giá Performance — Smart Document Reader (RAG System)

> Ngày đánh giá: 21/06/2026

---

## 1. Kiến trúc tổng quan

| Tầng | Công nghệ | Đánh giá |
|---|---|---|
| Frontend | Streamlit | Đơn giản, nhanh để prototype, không phù hợp production |
| Backend | FastAPI + SQLAlchemy | Tốt, async-capable, cấu trúc rõ ràng |
| Vector DB | ChromaDB (persistent) | Phù hợp local/offline, không cần server riêng |
| Embedding | `all-MiniLM-L6-v2` (SentenceTransformers) | Model nhỏ (~80MB), nhanh, chất lượng tạm cho tiếng Việt |
| LLM | Local LLM qua LM Studio (Gemma 3 4B) | 100% offline, nhưng hạn chế về chất lượng |
| Metadata DB | SQLite | Nhẹ, phù hợp single-user |

---

## 2. Điểm mạnh về Performance

### a) Cơ chế Full-Context / RAG tự động chuyển đổi

- Ngưỡng `FULL_CONTEXT_THRESHOLD_CHARS = 400,000` ký tự — với tài liệu nhỏ, hệ thống gửi 100% nội dung → chính xác hơn RAG search.
- Auto-detect context window của model qua API `/v1/models` → linh hoạt khi đổi model.

### b) Chunking chiến lược

- `CHUNK_SIZE = 600` từ, `CHUNK_OVERLAP = 80` từ → bước nhảy 520 từ.
- Overlap giữ context giữa các chunk, giảm mất thông tin tại biên.

### c) HTTP Connection Pool

- `httpx.Client` với `max_connections=10`, `max_keepalive_connections=5`, timeout 600s → reuse connection, giảm overhead khi gọi LLM nhiều lần.

### d) Quiz Micro-Batching (3 câu/lần)

- Giảm nguy cơ model nhỏ bị quá tải context, dễ parse hơn sinh JSON lớn.
- Fallback parse 3 lớp (JSON → Text format → Numbered) → robust với LLM hallucination.

### e) Summary Caching

- Lưu summary vào SQLite, lần sau trả về ngay (< 0.1s) — tránh gọi LLM lặp lại.

### f) Background Indexing

- Upload → trả response ngay, indexing chạy nền → UX không bị block.

---

## 3. Điểm yếu / Vấn đề Performance

### 🔴 Nghiêm trọng

| Vấn đề | Chi tiết | Ảnh hưởng |
|---|---|---|
| **Embedding model yếu cho tiếng Việt** | `all-MiniLM-L6-v2` được train chủ yếu trên tiếng Anh. Semantic search cho tiếng Việt sẽ kém chính xác. | RAG mode trả về chunks không liên quan, câu trả lời sai. |
| **Quiz chỉ dùng 1,200 ký tự/chunk** | `MAX_QUIZ_CONTENT_CHARS = 1200` → mỗi batch chỉ thấy ~600 token tiếng Việt. | Câu hỏi quiz hời hợt, không khai thác được ngữ cảnh sâu. |
| **Singleton LLMService không thread-safe** | Biến global `_llm_service_instance` không có lock. Background task + request đồng thời có thể race condition. | Crash hoặc corrupt state khi nhiều request cùng lúc. |
| **SQLite cho multi-user** | SQLite không hỗ trợ concurrent write tốt. | Lock contention khi nhiều user upload/hỏi đáp cùng lúc. |

### 🟡 Trung bình

| Vấn đề | Chi tiết |
|---|---|
| **Không có rate limiting** | Không giới hạn số request → user có thể flood LLM. |
| **Không cache RAG search** | Mỗi câu hỏi đều phải re-embed + vector search, dù hỏi cùng nội dung. |
| **`get_random_chunks_by_stem` scan toàn bộ collection** | `self._collection.get(limit=self._collection.count())` → load TẤT CẢ chunks vào RAM rồi filter. O(n) với mọi tài liệu. |
| **Không có connection retry** | LLM call fail → raise ngay, không retry. Network hiccup = user thấy lỗi. |
| **Temperature = 0.1 cứng** | Không cho phép user điều chỉnh. Quiz cần creativity cao hơn (0.4-0.7), Q&A cần thấp (0.1). |
| **History chỉ giữ 4-8 messages** | `messages[-4:]` / `messages[-8:]` → mất context hội thoại dài. |

### 🟢 Nhỏ

| Vấn đề | Chi tiết |
|---|---|
| `TOP_K_RESULTS = 15` | Lấy 15 chunks nhưng không rerank → nhiều chunks nhiễu trong context. |
| Không có chunk dedup | Upload trùng file → chunks nhân đôi trong ChromaDB. |
| CORS `allow_origins=["*"]` | Security risk, không phải performance nhưng cần fix. |

---

## 4. Đánh giá thuật toán Adaptive (BKT)

| Tiêu chí | Điểm | Nhận xét |
|---|---|---|
| **Độ chính xác** | 6/10 | BKT đơn giản hóa (3 params cố định), không calibrate theo user thực tế. |
| **Khả năng mở rộng** | 5/10 | `session_id` cố định theo user ID → không phân biệt nhiều session học. |
| **Tác động thực tế** | 7/10 | Ý tưởng tốt — quiz lần sau tập trung vào kiến thức yếu. Nhưng phụ thuộc chất lượng chunk mapping. |
| **Evaluation endpoints** | 8/10 | Có sẵn `/evaluate/bkt` với AUC-ROC, Log-Loss — rất tốt để đo lường. |

---

## 5. Ước tính Latency (với Local LLM Gemma 3 4B trên CPU)

| Thao tác | Thời gian ước tính |
|---|---|
| Upload + Index (10 trang PDF) | 5-15s (text extract + embed chunks) |
| Q&A Full-Context (tài liệu nhỏ) | 10-30s (phụ thuộc độ dài prompt) |
| Q&A RAG Mode | 5-15s (embed query + search + generate) |
| Tóm tắt (1 lần gọi) | 15-45s |
| Tóm tắt Map-Reduce (3 đoạn) | 60-180s (3× summarize + 1× total) |
| Quiz 10 câu (4 batch × LLM call) | 60-120s |
| Learning Path (1 LLM call) | 15-30s |

---

## 6. Khuyến nghị cải thiện Performance

| Ưu tiên | Cải thiện | Impact |
|---|---|---|
| 🔴 P0 | Đổi embedding model sang `keepn/sentence-transformers-phobert-base` hoặc `intfloat/multilingual-e5-small` | Tăng chất lượng RAG search tiếng Việt lên đáng kể |
| 🔴 P0 | Thêm retry logic (3 lần, exponential backoff) cho LLM calls | Giảm lỗi do network hiccup |
| 🟡 P1 | Cache vector search results (LRU cache theo query hash) | Giảm 50%+ latency cho câu hỏi lặp lại |
| 🟡 P1 | Thay `get_random_chunks_by_stem` bằng ChromaDB `where` filter | Tránh load toàn bộ collection vào RAM |
| 🟡 P1 | Thêm `threading.Lock` cho singleton LLMService | Tránh race condition |
| 🟢 P2 | Rerank chunks sau vector search (cross-encoder hoặc BM25 hybrid) | Tăng chất lượng context đưa vào LLM |
| 🟢 P2 | Cho phép user chỉnh temperature qua API | Tối ưu cho từng use case (quiz vs Q&A) |
| 🟢 P2 | Streaming response (SSE) cho LLM calls | UX tốt hơn — user thấy câu trả lời xuất hiện dần |

---

## 7. Tổng kết

| Khía cạnh | Điểm (10) |
|---|---|
| Kiến trúc | 7.5 |
| Code quality | 7.0 |
| RAG retrieval quality | 5.5 (do embedding tiếng Việt yếu) |
| LLM integration | 7.0 |
| Adaptive learning (BKT) | 7.0 |
| UX/Responsiveness | 6.0 (latency cao với local LLM) |
| Scalability | 4.0 (single-user, SQLite) |
| **Tổng** | **~6.3/10** |






















---

Đây là một prototype/bài tập tốt nghiệp solid với kiến trúc rõ ràng và nhiều tính năng thông minh (BKT, CoT, Full-Context/RAG hybrid). Điểm yếu lớn nhất là **embedding model không phù hợp tiếng Việt** và **phụ thuộc vào local LLM nhỏ** (Gemma 4B) khiến chất lượng câu trả lời và quiz bị giới hạn.
 ---

    Những gì ĐÃ CÓ (khá ấn tượng)

    1. System Prompt ch ống hallucination

     1 # config.py
     2 "Trả lời dựa HOÀN TOÀN vào nội dung tài liệu.
     3  Nếu thông tin không có trong tài liệu, hãy nói rõ điều đó.
     4  Không bịa đặt hay suy đoán ngoài phạm vi tài liệu."
    → Tốt, nhưng chỉ là "lời nhắc" — không có cơ chế强制执行 (enforcement).

    2. Source Attribution (trích dẫn nguồn)
     1 SourceInfo(file_name=fn, relevance_score=round(r.score, 3))
    → User thấy câu trả lời đến từ file nào + điểm liên quan.

    3. Full-Context Mode (giảm retrieval error)
    Khi tài liệu nhỏ (< 400K ký tự), gửi 100% nội dung → loại bỏ hoàn toàn rủi ro RAG lấy sai chunks.

    4. Hệ thống Evaluation 3 tầng (rất đáng ghi nhận)


    ┌──────────────────┬──────────────────┬────────────────────────────────────────────┐
    │ Tầng             │ Script           │ Tiêu chí                                   │
    ├──────────────────┼──────────────────┼────────────────────────────────────────────┤
    │ Tầng 1 — RAG Q&A │ evaluate_rag.py  │ Faithfulness, Relevancy, Context Precision │
    ├──────────────────┼──────────────────┼────────────────────────────────────────────┤
    │ Tầng 2 — BKT     │ evaluate_bkt.py  │ Accuracy, AUC-ROC, Log-Loss                │
    ├──────────────────┼──────────────────┼────────────────────────────────────────────┤
    │ Tầng 3 — Quiz    │ evaluate_quiz.py │ Groundedness, Plausibility                 │
    └──────────────────┴──────────────────┴────────────────────────────────────────────┘


    → Chạy tổng hợp qua run_all_evaluations.py, xuất CSV.

    ---

    Những gì CÒN THIẾU (quan trọng)

    🔴 Vấn đề nghiêm trọng


    ┌─────┬────────────────────────────┬─────────────────────────────────────────────────────────────────────────────────────────┐       
    │ #   │ Thiếu                      │ Tại sao quan trọng                                                                      │       
    ├─────┼────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────┤       
    │ 1   │ Không có runtime guardrail │ System prompt chỉ là "lời yêu cầu". LLM nhỏ (Gemma 4B) vẫn có thể hallucinate mà không  │       
    │     │                            │ có cơ chế nào phát hiện/block tại thời điểm trả lời.                                    │       
    ├─────┼────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────┤       
    │ 2   │ Không lọc chunks theo      │ Lấy 15 chunks nhưng không loại bỏ chunks có score quá thấp → đưa nhiễu vào context, LLM │       
    │     │ relevance score            │  bị confusion.                                                                          │       
    ├─────┼────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────┤       
    │ 3   │ Không verify answer ∈      │ Không có cơ chế hậu kiểm: đối chiếu câu trả lời với nội dung gốc để phát hiện thông tin │       
    │     │ document                   │  bịa đặt.                                                                               │       
    ├─────┼────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────┤       
    │ 4   │ LLM-as-Judge dùng cùng     │ Gemma 4B vừa sinh câu trả lời, vừa chấm điểm → tự chấm bài mình, bias nặng. Judge cần   │       
    │     │ model nhỏ                  │ model mạnh hơn hoặc phương pháp khác.                                                   │       
    ├─────┼────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────┤       
    │ 5   │ Không có confidence score  │ User không biết câu trả lời nào "chắc chắn" vs "không chắc". Hệ thống có                │       
    │     │                            │ relevance_score nhưng không aggregate thành confidence.                                 │       
    └─────┴────────────────────────────┴─────────────────────────────────────────────────────────────────────────────────────────┘       


    🟡 Vấn đề trung bình


    ┌─────┬───────────────────────────────┬──────────────────────────────────────────────────────────────────────────────────────┐       
    │ #   │ Thiếu                         │ Tại sao quan trọng                                                                   │       
    ├─────┼───────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────┤       
    │ 6   │ Không rerank chunks           │ Vector search (cosine similarity) chỉ là first-stage retrieval. Không có             │       
    │     │                               │ cross-encoder hay BM25 hybrid để sắp xếp lại.                                        │       
    ├─────┼───────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────┤       
    │ 7   │ Không có chunk dedup          │ Upload trùng file → chunks nhân đôi → LLM thấy cùng nội dung 2 lần → bias.           │       
    ├─────┼───────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────┤       
    │ 8   │ Không có "I don't know"       │ Không có logic: nếu tất cả chunks có score < ngưỡng → trả lời "Không tìm thấy thông  │       
    │     │ detection                     │ tin" thay vì cố sinh câu trả lời.                                                    │       
    ├─────┼───────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────┤       
    │ 9   │ Quiz không validate đáp án    │ Câu hỏiquiz sinh ra nhưng không kiểm tra xem đáp án A/B/C/D có thực sự nằm trong nội │       
    │     │ với document                  │  dung tài liệu không.                                                                │       
    ├─────┼───────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────┤       
    │ 10  │ Summary không có factuality   │ Tóm tắt Map-Reduce có thể mất thông tin hoặc thêm chi tiết không có trong gốc.       │       
    │     │ check                         │                                                                                      │       
    └─────┴───────────────────────────────┴──────────────────────────────────────────────────────────────────────────────────────┘       


    🟢 Vấn đề nhỏ


    ┌─────┬───────────────────────────────────────────────────────────────────────────┐
    │ #   │ Thiếu                                                                     │
    ├─────┼───────────────────────────────────────────────────────────────────────────┤
    │ 11  │ Không có feedback loop (user thumbs up/down)                              │
    ├─────┼───────────────────────────────────────────────────────────────────────────┤
    │ 12  │ Không có A/B testing prompt versions                                      │
    ├─────┼───────────────────────────────────────────────────────────────────────────┤
    │ 13  │ Không có output format validation cho Q&A (chỉ có quiz mới validate JSON) │
    └─────┴───────────────────────────────────────────────────────────────────────────┘

    ---

    So sánh với các hệ thống RAG production


    ┌──────────────────────────────┬─────────────────┬──────────────────────────────────────┐
    │ Cơ chế                       │ Hệ thống này    │ Production RAG                       │
    ├──────────────────────────────┼─────────────────┼──────────────────────────────────────┤
    │ Retrieval filter (min score) │ ❌              │ ✅ Threshold 0.7+                    │
    ├──────────────────────────────┼─────────────────┼──────────────────────────────────────┤
    │ Reranker (cross-encoder)     │ ❌              │ ✅ Cohere Rerank, BGE Reranker       │
    ├──────────────────────────────┼─────────────────┼──────────────────────────────────────┤
    │ Hallucination detector       │ ❌              │ ✅ RAGAS, TruLens, Guardrails AI     │
    ├──────────────────────────────┼─────────────────┼──────────────────────────────────────┤
    │ Confidence score             │ ❌              │ ✅ Aggregate similarity → confidence │
    ├──────────────────────────────┼─────────────────┼──────────────────────────────────────┤
    │ "I don't know" fallback      │ ❌              │ ✅ Reject if max_score < threshold   │
    ├──────────────────────────────┼─────────────────┼──────────────────────────────────────┤
    │ Citation verification        │ ❌              │ ✅ Verify claims against source      │
    ├──────────────────────────────┼─────────────────┼──────────────────────────────────────┤
    │ Human feedback loop          │ ❌              │ ✅ Thumbs up/down → fine-tune        │
    ├──────────────────────────────┼─────────────────┼──────────────────────────────────────┤
    │ LLM-as-Judge (independent)   │ ❌ (cùng model) │ ✅ Dùng GPT-4 chấm model nhỏ         │
    └──────────────────────────────┴─────────────────┴──────────────────────────────────────┘

    ---

    Tóm lại

    Đã làm tốt:
     - Evaluation framework 3 tầng (offline) — rất ít project sinh viên có
     - System prompt chống hallucination
     - Full-Context mode cho tài liệu nhỏ
     - Source attribution

    Cần bổ sung để đảm bảo chất lượng thực sự:
     1. P0 — Relevance threshold filter: Loại chunks có score < 0.5 trước khi đưa vào context
     2. P0 — "I don't know" fallback: Nếu max(relevance_scores) < 0.4 → trả lời "Không tìm thấy"
     3. P1 — Confidence score: Aggregate relevance scores thành confidence level cho user
     4. P1 — Output verification: Post-check: extract key claims từ answer, search trong document gốc
     5. P2 — Independent judge: Dùng API model lớn (GPT-4o-mini) làm judge thay vì cùng local model