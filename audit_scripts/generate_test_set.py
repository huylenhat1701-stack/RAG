import os
import sys
import json
import random
from pathlib import Path

# Add project paths
sys.path.insert(0, str(Path(__file__).parent.parent / 'rag_project'))
from backend.services.llm_service import get_llm_service

def main():
    llm_service = get_llm_service()
    # Check total chunks in ChromaDB
    total = llm_service._collection.count()
    print(f"Total chunks in ChromaDB: {total}")
    
    # Group by filename
    all_chunks = llm_service._collection.get(limit=total)
    ids = all_chunks.get("ids", [])
    documents = all_chunks.get("documents", [])
    metadatas = all_chunks.get("metadatas", [])
    
    doc_chunks = {}
    for idx, meta in enumerate(metadatas):
        fn = meta.get("filename", "unknown")
        if fn not in doc_chunks:
            doc_chunks[fn] = []
        doc_chunks[fn].append({
            "id": ids[idx],
            "text": documents[idx],
            "filename": fn
        })
    
    for fn, chunks in doc_chunks.items():
        print(f"File: {fn} -> {len(chunks)} chunks")
        
    test_cases = []
    
    # 1. Generate Factual Lookup Questions (10 cases)
    factual_chunks = []
    available_files = list(doc_chunks.keys())
    random.shuffle(available_files)
    
    # Try to pick chunks evenly from files
    for fn in available_files:
        chunks = doc_chunks[fn]
        selected_from_file = random.sample(chunks, min(3, len(chunks)))
        factual_chunks.extend(selected_from_file)
        if len(factual_chunks) >= 10:
            factual_chunks = factual_chunks[:10]
            break
            
    print(f"Generating {len(factual_chunks)} factual questions...")
    for idx, c in enumerate(factual_chunks):
        snippet = c["text"]
        prompt = (
            f"Dựa vào đoạn văn sau, hãy đặt ra 1 câu hỏi cụ thể, rõ ràng bằng tiếng Việt "
            f"và có câu trả lời nằm hoàn toàn trong đoạn văn đó.\n\n"
            f"Đoạn văn:\n{snippet}\n\n"
            f"Chỉ trả về câu hỏi, không thêm bất kỳ văn bản giải thích nào khác."
        )
        try:
            q = llm_service.chat_direct(
                prompt=prompt,
                system_prompt="Bạn là giáo viên đặt câu hỏi thi. Chỉ trả về câu hỏi."
            ).strip()
            q = q.replace('"', '').replace('“', '').replace('”', '')
            test_cases.append({
                "id": f"factual_{idx+1}",
                "type": "factual",
                "question": q,
                "filenames": [c["filename"]],
                "ground_truth_chunks": [c["id"]],
                "ground_truth_text": snippet
            })
            print(f"  Factual {idx+1}: {q}")
        except Exception as e:
            print(f"  Error generating factual Q for chunk {c['id']}: {e}")
            
    # 2. Generate Multi-chunk Questions (5 cases)
    print("Generating 5 multi-chunk questions...")
    multi_count = 0
    # Try to get 2 chunks from the same file
    for fn in available_files:
        if multi_count >= 5:
            break
        chunks = doc_chunks[fn]
        if len(chunks) < 2:
            continue
        selected_pair = random.sample(chunks, 2)
        c1, c2 = selected_pair[0], selected_pair[1]
        prompt = (
            f"Dựa vào hai đoạn văn sau đây từ cùng một tài liệu, hãy đặt ra 1 câu hỏi tổng hợp bằng tiếng Việt "
            f"mà để trả lời được cần kết hợp thông tin từ cả hai đoạn văn.\n\n"
            f"Đoạn văn 1:\n{c1['text'][:600]}\n\n"
            f"Đoạn văn 2:\n{c2['text'][:600]}\n\n"
            f"Chỉ trả về câu hỏi, không thêm bất kỳ văn bản giải thích nào khác."
        )
        try:
            q = llm_service.chat_direct(
                prompt=prompt,
                system_prompt="Bạn là giáo viên đặt câu hỏi thi. Chỉ trả về câu hỏi."
            ).strip()
            q = q.replace('"', '').replace('“', '').replace('”', '')
            test_cases.append({
                "id": f"multichunk_{multi_count+1}",
                "type": "multichunk",
                "question": q,
                "filenames": [fn],
                "ground_truth_chunks": [c1["id"], c2["id"]],
                "ground_truth_text": f"{c1['text']}\n\n[Đoạn tiếp theo]\n\n{c2['text']}"
            })
            print(f"  Multi-chunk {multi_count+1}: {q}")
            multi_count += 1
        except Exception as e:
            print(f"  Error generating multi-chunk Q for {fn}: {e}")
            
    # 3. Generate Out-of-domain / Adversarial Questions (5 cases)
    print("Generating 5 out-of-domain/adversarial questions...")
    ood_topics = [
        "Cách nấu món phở bò Hà Nội chuẩn vị truyền thống tại nhà?",
        "Danh sách các địa điểm du lịch nổi tiếng tại Đà Lạt và lịch trình 3 ngày 2 đêm?",
        "Tóm tắt tiểu sử và sự nghiệp của danh thủ bóng đá Lionel Messi?",
        "Làm thế nào để học lập trình web bằng ngôn ngữ Javascript cho người mới bắt đầu?",
        "Nguyên nhân và cách phòng ngừa bệnh cúm mùa vào mùa đông?"
    ]
    for idx, q in enumerate(ood_topics):
        test_cases.append({
            "id": f"adversarial_{idx+1}",
            "type": "adversarial",
            "question": q,
            "filenames": available_files,
            "ground_truth_chunks": [],
            "ground_truth_text": ""
        })
        print(f"  Adversarial {idx+1}: {q}")
        
    # Save to JSON
    out_dir = Path(__file__).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "test_set.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(test_cases, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] Saved {len(test_cases)} test cases to {out_path}")

if __name__ == "__main__":
    main()
