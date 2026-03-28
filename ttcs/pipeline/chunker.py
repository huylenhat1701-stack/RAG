import re
from typing import List


class TextChunker:
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, text: str) -> List[str]:
        if not text or not text.strip():
            return []

        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        units: List[str] = []

        for para in paragraphs:
            if len(para) <= self.chunk_size:
                units.append(para)
                continue
            sentences = [
                s.strip()
                for s in re.split(r"(?<=[.!?])\s+|\n", para)
                if s and s.strip()
            ]
            if sentences:
                units.extend(sentences)
            else:
                units.extend(
                    para[i : i + self.chunk_size] for i in range(0, len(para), self.chunk_size)
                )

        chunks: List[str] = []
        current = ""
        for unit in units:
            if len(unit) > self.chunk_size:
                for i in range(0, len(unit), self.chunk_size):
                    part = unit[i : i + self.chunk_size].strip()
                    if len(part) >= 50:
                        chunks.append(part)
                continue

            candidate = f"{current}\n{unit}".strip() if current else unit
            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                if len(current) >= 50:
                    chunks.append(current)
                overlap_text = current[-self.chunk_overlap :] if current else ""
                current = f"{overlap_text}\n{unit}".strip()

        if len(current) >= 50:
            chunks.append(current)

        return chunks

    def split_with_metadata(self, text: str, filename: str) -> List[dict]:
        chunks = self.split(text)
        results = []
        cursor = 0
        for idx, chunk in enumerate(chunks):
            pos = text.find(chunk, cursor)
            if pos == -1:
                pos = cursor
            results.append(
                {
                    "text": chunk,
                    "chunk_index": idx,
                    "filename": filename,
                    "char_start": pos,
                }
            )
            cursor = pos + len(chunk)
        return results
