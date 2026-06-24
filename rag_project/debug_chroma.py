import chromadb, sys
sys.stdout.reconfigure(encoding='utf-8')
# Backend dung backend/chroma_db
client = chromadb.PersistentClient(path='backend/chroma_db')
col = client.get_or_create_collection('rag_knowledge_base')

print("=== ChromaDB Debug (backend/chroma_db) ===")
try:
    print("Total chunks:", col.count())
except Exception as e:
    print("ERROR count:", e)
    import sys; sys.exit(1)

# Get sample with metadatas
r_all = col.get(limit=2316, include=["metadatas"])
filenames = set()
file_stems = set()
for m in r_all.get("metadatas", []):
    if m:
        fn = m.get("filename", "")
        fs = m.get("file_stem", "")
        if fn: filenames.add(fn)
        if fs: file_stems.add(fs)

print("\nAll unique filenames:")
for f in sorted(filenames):
    print("  filename:", repr(f))
print("\nAll unique file_stems:")
for f in sorted(file_stems):
    print("  file_stem:", repr(f))

# Test $contains
print("\n=== Testing filters ===")
try:
    r2 = col.get(where={"filename": {"$contains": "CNKHXH"}}, limit=3, include=["metadatas"])
    print(f"$contains 'CNKHXH': {len(r2.get('ids', []))} results")
    for m in r2.get("metadatas", [])[:2]:
        print("  -", m)
except Exception as e:
    print(f"$contains FAILED: {type(e).__name__}: {e}")

# Test exact match with Vietnamese filename
try:
    r3 = col.get(where={"filename": {"$in": ["Gi\u00e1o-tr\u00ecnh-CNKHXH_1.extracted.txt"]}}, limit=3, include=["metadatas"])
    print(f"\nExact filename 'Gi\u00e1o-tr\u00ecnh-CNKHXH_1.extracted.txt': {len(r3.get('ids', []))} results")
except Exception as e:
    print(f"Exact filename FAILED: {e}")
