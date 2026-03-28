import asyncio
import logging
import re
import time

import cohere
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from openai import AsyncOpenAI

import config

logger = logging.getLogger(__name__)

_GEMINI_RETRY_HINT = re.compile(r"Please retry in ([0-9]+(?:\.[0-9]+)?)s", re.IGNORECASE)


class ServiceUnavailableException(Exception):
    pass


def _gemini_retry_after_seconds(exc: BaseException) -> float:
    m = _GEMINI_RETRY_HINT.search(str(exc))
    if m:
        return min(float(m.group(1)) + 2.0, 120.0)
    return 40.0


def _is_gemini_quota_or_rate_limit(exc: BaseException) -> bool:
    if isinstance(exc, genai_errors.ClientError) and getattr(exc, "code", None) == 429:
        return True
    s = str(exc)
    return "RESOURCE_EXHAUSTED" in s or "429" in s and "quota" in s.lower()


class LLMService:
    def __init__(self):
        self.provider = config.LLM_PROVIDER.lower()
        self.openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY) if config.OPENAI_API_KEY else None
        self.cohere_client = cohere.AsyncClient(config.COHERE_API_KEY) if config.COHERE_API_KEY else None
        self.gemini_client = genai.Client(api_key=config.GEMINI_API_KEY) if config.GEMINI_API_KEY else None

    async def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        attempts = 5 if self.provider == "gemini" else 3
        last_error = None

        for attempt in range(1, attempts + 1):
            start_time = time.perf_counter()
            try:
                if self.provider == "openai":
                    output = await self._generate_openai(prompt, max_tokens)
                elif self.provider == "gemini":
                    output = await self._generate_gemini(prompt, max_tokens)
                elif self.provider == "cohere":
                    output = await self._generate_cohere(prompt, max_tokens)
                else:
                    raise ValueError(f"Provider không hỗ trợ: {self.provider}")

                latency = time.perf_counter() - start_time
                logger.info("LLM provider=%s latency=%.3fs", self.provider, latency)
                return output
            except Exception as exc:
                latency = time.perf_counter() - start_time
                logger.warning(
                    "LLM failed provider=%s attempt=%s latency=%.3fs error=%s",
                    self.provider,
                    attempt,
                    latency,
                    exc,
                )
                last_error = exc
                if attempt >= attempts:
                    break
                if self.provider == "gemini" and _is_gemini_quota_or_rate_limit(exc):
                    delay = _gemini_retry_after_seconds(exc)
                    logger.info("Gemini 429/quota: chờ %.1fs rồi thử lại (lần %s/%s)", delay, attempt, attempts)
                    await asyncio.sleep(delay)
                else:
                    await asyncio.sleep(2 ** (attempt - 1))

        if self.provider == "gemini" and last_error and _is_gemini_quota_or_rate_limit(last_error):
            raise ServiceUnavailableException(
                "Gemini API: hết quota hoặc vượt giới hạn (429). "
                "Gợi ý: (1) Trong .env đổi GEMINI_MODEL sang model khác (vd. gemini-2.5-flash, gemini-flash-lite-latest — xem AI Studio), "
                "(2) Đợi vài phút / sang ngày mới để reset quota, "
                "(3) Bật billing hoặc dùng project & API key mới. "
                "Chi tiết: https://ai.google.dev/gemini-api/docs/rate-limits"
            )
        raise ServiceUnavailableException(f"LLM service không khả dụng: {last_error}")

    async def _generate_openai(self, prompt: str, max_tokens: int) -> str:
        if not self.openai_client:
            raise ValueError("OPENAI_API_KEY chưa được cấu hình.")
        response = await self.openai_client.chat.completions.create(
            model=config.OPENAI_MODEL or "gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        return (response.choices[0].message.content or "").strip()

    async def _generate_gemini(self, prompt: str, max_tokens: int) -> str:
        if not self.gemini_client:
            raise ValueError("GEMINI_API_KEY chưa được cấu hình.")
        model = (config.GEMINI_MODEL or "gemini-2.5-flash").removeprefix("models/")
        response = await self.gemini_client.aio.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=max_tokens),
        )
        return (response.text or "").strip()

    async def _generate_cohere(self, prompt: str, max_tokens: int) -> str:
        if not self.cohere_client:
            raise ValueError("COHERE_API_KEY chưa được cấu hình.")
        response = await self.cohere_client.chat(
            model=config.COHERE_MODEL or "command-r",
            message=prompt,
            max_tokens=max_tokens,
        )
        return (response.text or "").strip()
