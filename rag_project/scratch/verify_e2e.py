import os
import sys
from pathlib import Path
from sqlalchemy.orm import Session

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag_project.backend.db.database import SessionLocal, Base, engine
from rag_project.backend.services.llm_service import get_llm_service
from rag_project.backend.services.rag_service import answer_question, generate_quiz
from rag_project.backend.repositories.document_repo import DocumentRepository
from rag_project.backend.models.domain import Document

def run_verification():
    print("=== BEGIN E2E VERIFICATION ===")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    try:
        # Step 1: Init LLM Service
        print("\n--- STEP 1: INITIALIZE COMPONENTS ---")
        llm_service = get_llm_service()
        print("Status:", llm_service.is_healthy())
        
        # Step 2: Indexing
        print("\n--- STEP 2: INDEXING ---")
        doc_repo = DocumentRepository(db)
        # Check if we have documents, if not we add a dummy one
        docs = doc_repo.get_indexed()
        doc_id = None
        if not docs:
            print("No documents found, inserting a dummy one...")
            dummy_path = PROJECT_ROOT / "rag_project" / "uploads" / "dummy.txt"
            dummy_path.parent.mkdir(exist_ok=True)
            dummy_path.write_text("Sơn Tùng M-TP sinh ngày 5 tháng 7 năm 1994. Quê quán ở Thái Bình. Sơn Tùng là ca sĩ nổi tiếng.", encoding="utf-8")
            doc = doc_repo.create(
                file_name="dummy.txt",
                file_path=str(dummy_path),
                file_hash="dummy_hash",
                file_size=100,
                status="indexed",
                user_id=None
            )
            llm_service.load_files_into_kb([str(dummy_path)])
            doc_id = doc.id
        else:
            print(f"Found {len(docs)} indexed documents. Re-indexing first one to check prefix.")
            doc = docs[0]
            doc_id = doc.id
            if os.path.exists(doc.file_path):
                llm_service.load_files_into_kb([doc.file_path])
            
        print("Indexing completed.")
        
        # Step 3: Q&A In-scope
        print("\n--- STEP 3: Q&A IN-SCOPE ---")
        print("Question: Sơn Tùng sinh năm bao nhiêu?")
        resp_in_scope = answer_question(
            question="Sơn Tùng sinh năm bao nhiêu?",
            top_k=3,
            db=db,
            llm_service=llm_service,
            doc_ids=[doc_id] if doc_id else None
        )
        print("Answer:", resp_in_scope.answer)
        print("Confidence:", resp_in_scope.confidence_score)
        print("Warning:", resp_in_scope.warning)
        
        # Step 4: Q&A Out-of-scope
        print("\n--- STEP 4: Q&A OUT-OF-SCOPE ---")
        print("Question: Cách nấu phở bò ngon nhất là gì?")
        resp_out = answer_question(
            question="Cách nấu phở bò ngon nhất là gì?",
            top_k=3,
            db=db,
            llm_service=llm_service,
            doc_ids=[doc_id] if doc_id else None
        )
        print("Answer:", resp_out.answer)
        print("Mode:", resp_out.mode)
        
        # Step 5: Claim Verification Test
        print("\n--- STEP 5: CLAIM VERIFICATION ---")
        context = "Sơn Tùng M-TP sinh ngày 5 tháng 7 năm 1994."
        claims_true = ["Sơn Tùng M-TP sinh năm 1994."]
        claims_false = ["Sơn Tùng M-TP sinh năm 2000."]
        claims_neutral = ["Sơn Tùng M-TP cao 1m70."]
        
        print("Testing true claim...")
        res_true = llm_service.verify_claims(context, claims_true)
        print("True Claim Result:", res_true)
        
        print("Testing false claim...")
        res_false = llm_service.verify_claims(context, claims_false)
        print("False Claim Result:", res_false)
        
        print("Testing neutral claim...")
        res_neutral = llm_service.verify_claims(context, claims_neutral)
        print("Neutral Claim Result:", res_neutral)
        
        # Step 6: Quiz Generation
        print("\n--- STEP 6: QUIZ GENERATION ---")
        if doc_id:
            try:
                quiz_resp = generate_quiz(doc_id=doc_id, count=1, db=db, llm_service=llm_service)
                print("Quiz Total:", quiz_resp.total)
                if quiz_resp.questions:
                    print("Sample Q:", quiz_resp.questions[0].question)
            except Exception as e:
                print("Quiz gen failed:", e)

    finally:
        db.close()
        print("\n=== E2E VERIFICATION COMPLETED ===")

if __name__ == "__main__":
    run_verification()
