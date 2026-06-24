import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.rag_service import generate_quiz
from backend.services.llm_service import LLMService
from backend.db.database import SessionLocal

db = SessionLocal()
llm = LLMService()

print("Generating quiz for doc 2...")
try:
    res = generate_quiz(doc_id=2, count=3, db=db, llm_service=llm, session_id="testuser")
    print("Result total:", res.total)
    print("Questions:", res.questions)
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    db.close()
