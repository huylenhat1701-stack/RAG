"""
conftest.py - Shared pytest fixtures for RAG project tests.
"""
import sys
import os
from pathlib import Path

# Thêm backend vào sys.path để import được các module
RAG_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(RAG_PROJECT_ROOT))
