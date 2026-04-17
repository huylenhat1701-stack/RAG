import sys
from pathlib import Path

_CODEX_DIR = r"C:\Users\HACOM\Documents\openai\codex_oauth_module"
sys.path.insert(0, str(Path(_CODEX_DIR).parent))

from codex_oauth_module.local_rag import LocalRAG

from codex_oauth_module.vector_store import VectorStore

try:
    print('Testing VectorStore directly')
    vs = VectorStore(collection_name="local_rag", persist_directory="chroma_db", embedding_model=None)
    print('Success')
except Exception as e:
    import traceback
    traceback.print_exc()

