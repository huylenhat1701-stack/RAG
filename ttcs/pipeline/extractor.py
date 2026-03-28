import os
from typing import List

from docx import Document
import pdfplumber
from PyPDF2 import PdfReader


class TextExtractor:
    def extract(self, file_path: str) -> str:
        extension = os.path.splitext(file_path)[1].lower()
        if extension == ".pdf":
            text = self._extract_pdf(file_path)
        elif extension == ".docx":
            text = self._extract_docx(file_path)
        elif extension == ".txt":
            text = self._extract_txt(file_path)
        else:
            raise ValueError(f"File type không hỗ trợ: {extension}")
        return self._post_process(text)

    def _extract_pdf(self, file_path: str) -> str:
        reader = PdfReader(file_path)
        pages: List[str] = []
        for idx, page in enumerate(reader.pages, start=1):
            content = (page.extract_text() or "").strip()
            if not content:
                continue
            pages.append(f"--- Page {idx} ---\n{content}")
        merged = "\n\n".join(pages)
        if merged.strip():
            return merged
        return self._extract_pdf_pdfplumber(file_path)

    def _extract_pdf_pdfplumber(self, file_path: str) -> str:
        pages: List[str] = []
        with pdfplumber.open(file_path) as pdf:
            for idx, page in enumerate(pdf.pages, start=1):
                content = (page.extract_text() or "").strip()
                if not content:
                    continue
                pages.append(f"--- Page {idx} ---\n{content}")
        return "\n\n".join(pages)

    def _extract_docx(self, file_path: str) -> str:
        doc = Document(file_path)
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
        return "\n".join(paragraphs)

    def _extract_txt(self, file_path: str) -> str:
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                return file.read()
        except UnicodeDecodeError:
            with open(file_path, "r", encoding="latin-1") as file:
                return file.read()

    def _post_process(self, text: str) -> str:
        cleaned = text.replace("\x00", "")
        cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.strip() for line in cleaned.split("\n")]
        return "\n".join(line for line in lines if line).strip()
