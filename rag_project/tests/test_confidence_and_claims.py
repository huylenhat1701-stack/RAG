"""
Test script for confidence score and claim verification (hallucination detection).
Run with: pytest tests/test_confidence_and_claims.py -s -v
"""
import pytest
import numpy as np
from unittest.mock import MagicMock
from backend.services.rag_service import answer_question

@pytest.fixture
def mock_llm_service(mocker):
    llm = MagicMock()
    llm._model_name = "test_model"
    llm._embedding_model.encode = MagicMock(return_value=np.array([[0.9, 0.1]])) # Dummy embeddings
    return llm

@pytest.fixture
def mock_db(mocker):
    return MagicMock()

def test_confidence_score_calculation(mocker, mock_llm_service, mock_db):
    # Mock search results with known scores
    chunk1 = MagicMock()
    chunk1.chunk.text = "This is context A."
    chunk1.chunk.filename = "doc1.txt"
    chunk1.score = 0.8
    
    chunk2 = MagicMock()
    chunk2.chunk.text = "This is context B."
    chunk2.chunk.filename = "doc2.txt"
    chunk2.score = 0.9

    mock_llm_service.search.return_value = [chunk1, chunk2]
    mock_llm_service.generate_answer.return_value = "This is context A. This is context B."

    # We patch RELEVANCE_THRESHOLD and NO_CONTEXT_THRESHOLD
    mocker.patch('backend.services.rag_service.RELEVANCE_THRESHOLD', 0.5)
    mocker.patch('backend.services.rag_service.NO_CONTEXT_THRESHOLD', 0.4)

    mock_hist_repo = mocker.patch('backend.services.rag_service.HistoryRepository').return_value
    mock_hist_repo.create.return_value = MagicMock(id=1)

    response = answer_question(
        question="Test",
        history=[],
        db=mock_db,
        llm_service=mock_llm_service,
        user_id="user1",
        top_k=3,
        doc_ids=None
    )

    # Expected confidence = (0.8^2 + 0.9^2) / (0.8 + 0.9)
    expected_conf = (0.64 + 0.81) / 1.7
    assert round(response.confidence_score, 3) == round(expected_conf, 3)
    assert response.warning is None
