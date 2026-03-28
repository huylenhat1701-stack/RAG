import time
from functools import lru_cache
from typing import List

import cohere
from google import genai
from google.genai import types
from openai import OpenAI

import config


def _genai_embed_model_id(model: str) -> str:
    # Gemini Developer API (google-genai): dùng gemini-embedding-001, không dùng text-embedding-004 cho embedContent.
    return (model or "gemini-embedding-001").strip().removeprefix("models/")


class TextEmbedder:
    def __init__(self):
        self.provider = config.EMBEDDING_PROVIDER.lower()
        self.model = config.EMBEDDING_MODEL
        self.openai_client = OpenAI(api_key=config.OPENAI_API_KEY) if config.OPENAI_API_KEY else None
        self.cohere_client = cohere.Client(config.COHERE_API_KEY) if config.COHERE_API_KEY else None
        self._gemini_client = (
            genai.Client(api_key=config.GEMINI_API_KEY)
            if self.provider == "gemini" and config.GEMINI_API_KEY
            else None
        )

    @lru_cache(maxsize=1024)
    def embed_single(self, text: str) -> List[float]:
        if self.provider == "cohere":
            return self._embed_cohere([text], input_type="search_query")[0]
        if self.provider == "gemini":
            return self._embed_gemini([text], task_type="retrieval_query")[0]
        return self._embed_openai([text])[0]

    def embed_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        if self.provider == "gemini":
            batch_size = min(batch_size, 32)
        vectors: List[List[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            retry = 0
            while True:
                try:
                    if self.provider == "cohere":
                        vectors.extend(self._embed_cohere(batch, input_type="search_document"))
                    elif self.provider == "gemini":
                        vectors.extend(self._embed_gemini(batch, task_type="retrieval_document"))
                    else:
                        vectors.extend(self._embed_openai(batch))
                    break
                except Exception:
                    retry += 1
                    if retry >= 3:
                        raise
                    time.sleep(2**retry)
        return vectors

    def _embed_gemini(self, texts: List[str], task_type: str) -> List[List[float]]:
        if not self._gemini_client:
            raise ValueError("GEMINI_API_KEY chưa được cấu hình.")
        model = _genai_embed_model_id(self.model)
        tt = "RETRIEVAL_QUERY" if task_type.lower() in {"retrieval_query", "query"} else "RETRIEVAL_DOCUMENT"
        response = self._gemini_client.models.embed_content(
            model=model,
            contents=texts if len(texts) > 1 else texts[0],
            config=types.EmbedContentConfig(task_type=tt),
        )
        if not response.embeddings:
            return []
        return [list(emb.values) for emb in response.embeddings]

    def _embed_openai(self, texts: List[str]) -> List[List[float]]:
        if not self.openai_client:
            raise ValueError("OPENAI_API_KEY chưa được cấu hình.")
        response = self.openai_client.embeddings.create(
            model=self.model or "text-embedding-3-small",
            input=texts,
        )
        return [item.embedding for item in response.data]

    def _embed_cohere(self, texts: List[str], input_type: str = "search_document") -> List[List[float]]:
        if not self.cohere_client:
            raise ValueError("COHERE_API_KEY chưa được cấu hình.")
        response = self.cohere_client.embed(
            texts=texts,
            model=self.model or "embed-english-v3.0",
            input_type=input_type,
        )
        return response.embeddings
