"""
prompt.py – Prompt duy nhất, tái sử dụng được cho các AI agents khác nhau.

Cách dùng cơ bản:
    from prompt import build_rag_prompt

    prompt_text = build_rag_prompt(context="...", question="...")
    answer = your_llm_client.generate(prompt_text)

Cách dùng nâng cao (tuỳ chỉnh system prompt):
    from prompt import build_rag_prompt, SYSTEM_PROMPT, RAG_PROMPT_TEMPLATE

    custom_system = SYSTEM_PROMPT + "\\n\\nLưu ý thêm: chỉ trả lời bằng tiếng Anh."
    prompt_text = build_rag_prompt(context="...", question="...", system_prompt=custom_system)
"""

# ---------------------------------------------------------------------------
# System prompt – hành vi mặc định của agent
# ---------------------------------------------------------------------------
SYSTEM_PROMPT: str = (
    "Bạn là trợ lý hỏi đáp thông minh, trả lời chính xác và súc tích dựa trên "
    "ngữ cảnh được cung cấp. "
    "Nếu không tìm thấy thông tin liên quan trong ngữ cảnh, hãy nói rõ điều đó "
    "thay vì bịa đặt câu trả lời."
)

# ---------------------------------------------------------------------------
# Template – điền {context} và {question} để tạo prompt hoàn chỉnh
# ---------------------------------------------------------------------------
RAG_PROMPT_TEMPLATE: str = """{system_prompt}

NGỮ CẢNH:
{context}

CÂU HỎI: {question}

TRẢ LỜI (nếu không tìm thấy thông tin liên quan, hãy nói rõ):"""

# Giá trị mặc định khi không có ngữ cảnh
_NO_CONTEXT_PLACEHOLDER: str = "(không có ngữ cảnh)"


def build_rag_prompt(
    context: str,
    question: str,
    system_prompt: str = SYSTEM_PROMPT,
) -> str:
    """Tạo prompt hoàn chỉnh để gửi cho bất kỳ LLM nào.

    Args:
        context:       Các đoạn văn bản liên quan lấy từ vector store,
                       ngăn cách nhau bằng "\\n\\n---\\n\\n".
        question:      Câu hỏi của người dùng.
        system_prompt: System prompt tuỳ chỉnh (mặc định dùng SYSTEM_PROMPT).

    Returns:
        Chuỗi prompt hoàn chỉnh sẵn sàng gửi cho LLM.
    """
    stripped_context = context.strip() if context else ""
    filled_context = stripped_context if stripped_context else _NO_CONTEXT_PLACEHOLDER
    return RAG_PROMPT_TEMPLATE.format(
        system_prompt=system_prompt.strip(),
        context=filled_context,
        question=question.strip(),
    )
