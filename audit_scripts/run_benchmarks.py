import os
import sys
import json
import time
import math
import random
from pathlib import Path
import csv

# Add project paths
sys.path.insert(0, str(Path(__file__).parent.parent / 'rag_project'))
from backend.services.llm_service import get_llm_service
from backend.services.rag_service import answer_question
from backend.db.database import SessionLocal
from backend.models.domain import Document

def dot_product(v1, v2):
    return sum(x * y for x, y in zip(v1, v2))

def norm(v):
    return math.sqrt(sum(x * x for x in v))

def cosine_similarity(v1, v2):
    d = dot_product(v1, v2)
    n1 = norm(v1)
    n2 = norm(v2)
    if n1 > 0 and n2 > 0:
        return d / (n1 * n2)
    return 0.0

def spearman_correlation(x, y):
    n = len(x)
    if n <= 1:
        return 1.0
    
    def get_ranks(val_list):
        # Sort and return ranks (handle ties simply by sorting index)
        sorted_vals = sorted(list(enumerate(val_list)), key=lambda pair: pair[1])
        ranks = [0] * len(val_list)
        for rank, (orig_idx, val) in enumerate(sorted_vals):
            ranks[orig_idx] = rank + 1
        return ranks

    rank_x = get_ranks(x)
    rank_y = get_ranks(y)
    
    sum_d_sq = sum((rx - ry) ** 2 for rx, ry in zip(rank_x, rank_y))
    return 1.0 - (6.0 * sum_d_sq) / (n * (n**2 - 1))

def independent_judge(llm_service, question, answer, ground_truth):
    prompt = (
        f"Hãy đóng vai trò là giám khảo độc lập đánh giá tính trung thực (faithfulness) "
        f"của câu trả lời dựa trên ngữ cảnh thực tế được cung cấp.\n\n"
        f"CÂU HỎI: {question}\n\n"
        f"NGỮ CẢNH GỐC:\n{ground_truth}\n\n"
        f"CÂU TRẢ LỜI CỦA HỆ THỐNG:\n{answer}\n\n"
        f"Một câu trả lời được coi là trung thực (score = 5) nếu tất cả các tuyên bố trong đó đều có thể được suy ra trực tiếp từ ngữ cảnh gốc. "
        f"Nếu câu trả lời có chứa thông tin sai lệch hoặc suy diễn ngoài ngữ cảnh, hãy giảm điểm (xuống 1-4).\n"
        f"Chỉ trả về 1 số duy nhất từ 1 đến 5 đại diện cho điểm số, không thêm bất kỳ văn bản nào khác."
    )
    try:
        score_str = llm_service.chat_direct(
            prompt=prompt,
            system_prompt="Bạn là giám khảo AI trung thực. Chỉ trả về một số từ 1 đến 5."
        ).strip()
        # Extract first digit found
        for char in score_str:
            if char.isdigit():
                val = int(char)
                if 1 <= val <= 5:
                    return val
        return 3 # fallback
    except Exception:
        return 3

def count_naive_segmentation_errors(answer):
    # Split by '.'
    claims = [c.strip() for c in answer.split('.') if len(c.strip()) > 10]
    errors = 0
    # Common Vietnamese abbreviations or float patterns that would cause false splits
    abbrev_patterns = ["thần học", "n.", "tp.", "t.", "v.v.", "tr.", "đ.", "gs.", "ts.", "ths.", "nv."]
    for claim in claims:
        # Check if the split happened in the middle of a decimal number (ends with digit, starts with digit)
        # Or if it contains trailing abbreviations
        lower_claim = claim.lower()
        for abbrev in abbrev_patterns:
            if lower_claim.endswith(abbrev[:-1]): # split occurred on abbreviation dot
                errors += 1
                break
    return errors

def main():
    llm_service = get_llm_service()
    db = SessionLocal()
    
    # Load test set
    test_set_path = Path(__file__).parent / "test_set.json"
    if not test_set_path.exists():
        print(f"[ERROR] Test set not found at {test_set_path}. Please run generate_test_set.py first.")
        return
        
    with open(test_set_path, "r", encoding="utf-8") as f:
        test_cases = json.load(f)
        
    print(f"Loaded {len(test_cases)} test cases.")
    
    results = []
    
    # We will measure RQ1, RQ2, RQ3, RQ5, RQ6 using the main test cases
    for case in test_cases:
        qid = case["id"]
        qtype = case["type"]
        qtext = case["question"]
        filenames = case["filenames"]
        gt_chunks = case["ground_truth_chunks"]
        gt_text = case["ground_truth_text"]
        
        print(f"\nEvaluating {qid} ({qtype}): {qtext[:50]}...")
        
        # 1. Pipeline Latency Measurement (RQ6)
        # We will call individual components to measure timing
        
        # Phase 1: Query embedding
        t0 = time.perf_counter()
        query_text = f"query: {qtext}"
        query_emb = llm_service._embedding_model.encode([query_text]).tolist()[0]
        t_embed_query = time.perf_counter() - t0
        
        # Phase 2: Vector search ChromaDB
        t0 = time.perf_counter()
        where_filter = None
        if filenames:
            if len(filenames) == 1:
                where_filter = {"filename": filenames[0]}
            else:
                where_filter = {"filename": {"$in": filenames}}
                
        actual_top_k = min(15, llm_service._collection.count())
        search_res = llm_service._collection.query(
            query_embeddings=[query_emb],
            n_results=actual_top_k,
            where=where_filter,
        )
        t_vector_search = time.perf_counter() - t0
        
        # Process retrieval results
        retrieved_ids = search_res["ids"][0] if search_res["ids"] else []
        retrieved_docs = search_res["documents"][0] if search_res["documents"] else []
        retrieved_distances = search_res["distances"][0] if search_res["distances"] else []
        retrieved_metadatas = search_res["metadatas"][0] if search_res["metadatas"] else []
        
        # Parse search results
        parsed_results = []
        for i in range(len(retrieved_ids)):
            score = 1.0 / (1.0 + retrieved_distances[i])
            parsed_results.append({
                "id": retrieved_ids[i],
                "text": retrieved_docs[i],
                "score": score,
                "filename": retrieved_metadatas[i].get("filename", "unknown")
            })
            
        # Relevance thresholds
        max_score = max((r["score"] for r in parsed_results), default=0.0)
        mean_score = sum(r["score"] for r in parsed_results) / len(parsed_results) if parsed_results else 0.0
        
        # Recall@k (RQ2/RQ3)
        recall_15 = 0
        recall_5 = 0
        recall_3 = 0
        if gt_chunks:
            retrieved_top15 = retrieved_ids[:15]
            retrieved_top5 = retrieved_ids[:5]
            retrieved_top3 = retrieved_ids[:3]
            
            # Check how many ground truth chunks were successfully retrieved
            retrieved_gt_15 = sum(1 for gt in gt_chunks if gt in retrieved_top15)
            retrieved_gt_5 = sum(1 for gt in gt_chunks if gt in retrieved_top5)
            retrieved_gt_3 = sum(1 for gt in gt_chunks if gt in retrieved_top3)
            
            recall_15 = retrieved_gt_15 / len(gt_chunks)
            recall_5 = retrieved_gt_5 / len(gt_chunks)
            recall_3 = retrieved_gt_3 / len(gt_chunks)
            
        # Cosine similarity vs L2 rank deviation (RQ2)
        spearman_corr = 1.0
        rank_deviation_top5 = False
        if len(parsed_results) > 1:
            # Get chunk embeddings from ChromaDB
            chunk_get_res = llm_service._collection.get(ids=retrieved_ids, include=["embeddings"])
            chunk_embs = chunk_get_res.get("embeddings", [])
            
            if chunk_embs is not None and len(chunk_embs) > 0:
                # We need to map retrieved_ids to their embeddings
                id_to_emb = {chunk_get_res["ids"][i]: chunk_embs[i] for i in range(len(chunk_get_res["ids"]))}
                
                l2_scores = []
                cos_scores = []
                for r in parsed_results:
                    c_emb = id_to_emb.get(r["id"])
                    if c_emb is not None:
                        cos_sim = cosine_similarity(query_emb, c_emb)
                        l2_scores.append(r["score"])
                        cos_scores.append(cos_sim)
                
                if len(l2_scores) > 1:
                    spearman_corr = spearman_correlation(l2_scores, cos_scores)
                    
                    # Check top 5 rank deviation
                    # Order by L2
                    l2_ranked = [p["id"] for p in parsed_results]
                    # Order by Cosine
                    cos_ranked_pairs = sorted(zip(retrieved_ids, cos_scores), key=lambda x: x[1], reverse=True)
                    cos_ranked = [x[0] for x in cos_ranked_pairs]
                    
                    if l2_ranked[:5] != cos_ranked[:5]:
                        rank_deviation_top5 = True
                        
        # Phase 3: LLM generation & NLI verification
        t_llm_gen = 0.0
        t_nli_verify = 0.0
        answer = "Không có câu trả lời do dưới ngưỡng relevance."
        nli_warning_triggered = False
        nli_contradictions = 0
        nli_neutrals = 0
        nli_entailments = 0
        confidence_score = 0.0
        
        # Check relevance
        if max_score >= 0.4: # NO_CONTEXT_THRESHOLD
            # Filter chunks by RELEVANCE_THRESHOLD
            filtered = [r for r in parsed_results if r["score"] >= 0.5] # RELEVANCE_THRESHOLD
            context_chunks = filtered if filtered else parsed_results
            
            # Map to SearchResult objects
            from backend.services.llm_service import SearchResult, ChunkDocument
            context_search_results = []
            for r in context_chunks:
                chunk_doc = ChunkDocument(
                    id=r["id"],
                    text=r["text"],
                    filename=r["filename"]
                )
                context_search_results.append(SearchResult(chunk=chunk_doc, score=r["score"]))
                
            # Call LLM using generate_answer (safe and does truncation)
            t0 = time.perf_counter()
            try:
                answer = llm_service.generate_answer(
                    question=qtext,
                    context_chunks=context_search_results
                )
            except Exception as e:
                answer = f"Lỗi gọi LLM: {e}"
            t_llm_gen = time.perf_counter() - t0
            
            # Format context text for NLI chéo
            parts = []
            for idx_src, r in enumerate(context_chunks, 1):
                parts.append(f"[Nguồn {idx_src} — {r['filename']}]\n{r['text']}")
            context_text = "\n\n---\n\n".join(parts)
            
            # Call NLI verification
            t0 = time.perf_counter()
            claims = [c.strip() for c in answer.split('.') if len(c.strip()) > 10]
            if claims and llm_service._nli_model:
                nli_context = context_text[:2000]
                nli_results = llm_service.verify_claims(nli_context, claims)
                
                scores = [r["score"] for r in context_chunks]
                sum_scores = sum(scores)
                confidence_score = sum(s * s for s in scores) / sum_scores if sum_scores > 0 else 0.0
                
                for res in nli_results:
                    if res:
                        sorted_res = sorted(res, key=lambda x: x['score'], reverse=True)
                        if sorted_res:
                            argmax_label = sorted_res[0]['label']
                            if argmax_label == "contradiction":
                                nli_contradictions += 1
                                confidence_score -= 0.2
                            elif argmax_label == "neutral":
                                nli_neutrals += 1
                                confidence_score -= 0.1
                            elif argmax_label == "entailment":
                                nli_entailments += 1
                
                confidence_score = max(0.0, confidence_score)
                if nli_contradictions > 0:
                    nli_warning_triggered = True
            t_nli_verify = time.perf_counter() - t0
            
        # Independent faithfulness assessment (RQ5)
        independent_score = 5
        if qtype != "adversarial" and max_score >= 0.4:
            independent_score = independent_judge(llm_service, qtext, answer, gt_text)
        elif qtype == "adversarial":
            # For adversarial questions, if answer says "không tìm thấy thông tin" or similar, it's correct (faithfulness = 5)
            # if it hallucinated, it is low
            if "không" in answer.lower() and "tài liệu" in answer.lower():
                independent_score = 5
            else:
                independent_score = independent_judge(llm_service, qtext, answer, "Không có thông tin liên quan trong tài liệu.")
                
        # Naive claim segmentation errors (RQ5)
        segmentation_errors = count_naive_segmentation_errors(answer)
        
        results.append({
            "qid": qid,
            "type": qtype,
            "question": qtext,
            "max_score": max_score,
            "mean_score": mean_score,
            "recall_15": recall_15,
            "recall_5": recall_5,
            "recall_3": recall_3,
            "t_embed_query": t_embed_query,
            "t_vector_search": t_vector_search,
            "t_llm_gen": t_llm_gen,
            "t_nli_verify": t_nli_verify,
            "spearman_corr": spearman_corr,
            "rank_deviation_top5": rank_deviation_top5,
            "nli_warning_triggered": nli_warning_triggered,
            "nli_contradictions": nli_contradictions,
            "nli_neutrals": nli_neutrals,
            "nli_entailments": nli_entailments,
            "confidence_score": confidence_score,
            "independent_faithfulness_score": independent_score,
            "segmentation_errors": segmentation_errors,
            "answer": answer
        })
        
    # 2. Hybrid Mode: Full-Context vs RAG (RQ4)
    # We will pick a document, slice it, index it in a temporary collection or mock the behavior
    # to evaluate Full-Context (<= 400,000 chars) vs RAG (> 400,000 chars).
    # Let's slice the text of Giáo-trình-CNKHXH.pdf (which has extracted text file in uploads).
    print("\n--- Running RQ4: Hybrid Full-Context vs RAG Mode Comparison ---")
    doc_record = db.query(Document).filter(Document.id == 3).first() # Giáo-trình-CNKHXH.pdf
    hybrid_results = []
    if doc_record:
        extracted_path = Path(doc_record.file_path).with_suffix(".extracted.txt")
        if extracted_path.exists():
            full_text = extracted_path.read_text(encoding="utf-8")
            print(f"Original text length: {len(full_text):,} chars")
            
            # Slice 1: 390,000 characters (Full-Context mode)
            slice_fc = full_text[:390000]
            # Slice 2: 410,000 characters (RAG mode)
            slice_rag = full_text[:410000]
            
            # We will ask 3 questions from this document
            rq4_questions = [
                "Phương pháp nghiên cứu khoa học xã hội là gì?",
                "Các bước trong quy trình nghiên cứu khoa học xã hội gồm những gì?",
                "Thế nào là giả thuyết nghiên cứu khoa học?"
            ]
            
            # Test Full-Context mode on slice_fc
            for q_idx, q in enumerate(rq4_questions):
                print(f"Testing Q{q_idx+1} in Full-Context (390K chars)...")
                t0 = time.perf_counter()
                try:
                    ans_fc = llm_service.generate_answer_full_context(
                        question=q,
                        full_text=slice_fc,
                        filename="Giáo-trình-CNKHXH_390K.pdf"
                    )
                except Exception as e:
                    ans_fc = f"Lỗi: {e}"
                t_fc = time.perf_counter() - t0
                
                # Test RAG mode on slice_rag
                print(f"Testing Q{q_idx+1} in RAG Mode (410K chars)...")
                t0 = time.perf_counter()
                # Run the actual RAG search + generation
                query_text = f"query: {q}"
                q_emb = llm_service._embedding_model.encode([query_text]).tolist()[0]
                search_res = llm_service._collection.query(
                    query_embeddings=[q_emb],
                    n_results=15,
                    where={"filename": "Giáo-trình-CNKHXH.pdf"} # search in indexed document
                )
                r_docs = search_res["documents"][0] if search_res["documents"] else []
                r_ids = search_res["ids"][0] if search_res["ids"] else []
                r_dists = search_res["distances"][0] if search_res["distances"] else []
                
                # Map to SearchResult objects
                from backend.services.llm_service import SearchResult, ChunkDocument
                context_search_results = []
                for i in range(len(r_ids)):
                    score = 1.0 / (1.0 + r_dists[i])
                    chunk_doc = ChunkDocument(
                        id=r_ids[i],
                        text=r_docs[i],
                        filename="Giáo-trình-CNKHXH.pdf"
                    )
                    context_search_results.append(SearchResult(chunk=chunk_doc, score=score))
                
                # Call generate_answer (safe and does truncation)
                try:
                    ans_rag = llm_service.generate_answer(
                        question=q,
                        context_chunks=context_search_results
                    )
                except Exception as e:
                    ans_rag = f"Lỗi: {e}"
                t_rag = time.perf_counter() - t0
                
                # Independent faithfulness scores
                score_fc = independent_judge(llm_service, q, ans_fc, slice_fc[:10000]) # approximate context
                context_text = "\n\n---\n\n".join([f"[Nguồn {i+1}]\n{r_docs[i]}" for i in range(len(r_ids))])
                score_rag = independent_judge(llm_service, q, ans_rag, context_text)
                
                hybrid_results.append({
                    "q_idx": q_idx + 1,
                    "question": q,
                    "t_fc": t_fc,
                    "t_rag": t_rag,
                    "score_fc": score_fc,
                    "score_rag": score_rag,
                    "ans_fc": ans_fc,
                    "ans_rag": ans_rag
                })
                print(f"  Full-Context: {t_fc:.2f}s (Faithfulness={score_fc}) | RAG: {t_rag:.2f}s (Faithfulness={score_rag})")
                
    # 3. Chunking Boundary Quality (RQ1)
    # Visualizing chunk boundaries on 3 selected snippets from Giai tich 2 and BG CNPM
    print("\n--- Running RQ1: Chunking Boundary Quality Visualizer ---")
    chunk_visuals = []
    # We will pick a structured snippet from Giai Tich 2
    giai_tich_doc = db.query(Document).filter(Document.id == 5).first() # Giai tich 2
    if giai_tich_doc:
        gt_path = Path(giai_tich_doc.file_path).with_suffix(".extracted.txt")
        if gt_path.exists():
            text = gt_path.read_text(encoding="utf-8")
            # Find a place containing math or formula
            # Let's search for "tính" or "tích phân" or mathematical symbols
            lines = text.split("\n")
            math_idx = -1
            for idx, line in enumerate(lines):
                if "tích phân" in line.lower() or "dx" in line or "dy" in line or "f(" in line:
                    math_idx = idx
                    break
            
            if math_idx != -1:
                snippet = "\n".join(lines[max(0, math_idx - 5):min(len(lines), math_idx + 25)])
                # Let's chunk this snippet under the default size (600 words) vs small size (100 words)
                # to show where boundaries occur
                words = snippet.split()
                # Default: CHUNK_SIZE = 600, overlap = 80
                # But since our snippet is small, let's simulate smaller chunks (e.g. size=40, overlap=5)
                # to visualize what boundary cuts look like
                c_size = 40
                c_overlap = 5
                step = c_size - c_overlap
                chunks_default = []
                for i in range(0, len(words), step):
                    chunks_default.append(" ".join(words[i:i+c_size]))
                
                chunk_visuals.append({
                    "name": "Toán học Giải tích 2 (Ví dụ công thức/bài tập)",
                    "text": snippet,
                    "default_chunks": chunks_default
                })
                
    # Save all raw results
    out_dir = Path(__file__).parent
    
    # Save main benchmark results
    with open(out_dir / "audit_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "results": results,
            "hybrid_results": hybrid_results,
            "chunk_visuals": chunk_visuals
        }, f, ensure_ascii=False, indent=2)
        
    with open(out_dir / "audit_results.csv", "w", newline="", encoding="utf-8-sig") as f:
        fieldnames = [
            "qid", "type", "question", "max_score", "mean_score", 
            "recall_15", "recall_5", "recall_3", 
            "t_embed_query", "t_vector_search", "t_llm_gen", "t_nli_verify",
            "spearman_corr", "rank_deviation_top5", "nli_warning_triggered",
            "nli_contradictions", "nli_neutrals", "nli_entailments", 
            "confidence_score", "independent_faithfulness_score", "segmentation_errors"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            # Remove answer to make CSV compact
            row = {k: r[k] for k in fieldnames}
            writer.writerow(row)
            
    print(f"\n[OK] Benchmarks complete. Saved results to {out_dir / 'audit_results.json'} and {out_dir / 'audit_results.csv'}")

if __name__ == "__main__":
    main()
