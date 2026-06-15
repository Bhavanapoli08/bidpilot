"""
Small AI provider adapter for generation and embeddings.

The RAG pipeline was originally OpenAI-only. This wrapper keeps the rest of the
pipeline provider-neutral while preserving the same return shapes.
"""
import json
import logging
import time
from typing import Any, Dict, List, Optional

import requests
from openai import APIError, OpenAI, RateLimitError

from app.config import settings

logger = logging.getLogger(__name__)


class AIClient:
    def __init__(self):
        configured = (settings.AI_PROVIDER or "").strip().lower()
        if configured == "gemini" or (settings.GEMINI_API_KEY and not settings.OPENAI_API_KEY):
            self.provider = "gemini"
        else:
            self.provider = "openai"

        self.openai_client = None
        if self.provider == "openai":
            self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

        self.max_retries = 5

    @property
    def generation_model(self) -> str:
        if self.provider == "gemini":
            return settings.GEMINI_MODEL or settings.OPENAI_MODEL
        return settings.OPENAI_MODEL

    @property
    def embedding_model(self) -> str:
        if self.provider == "gemini":
            return settings.GEMINI_EMBEDDING_MODEL
        return settings.OPENAI_EMBEDDING_MODEL

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if self.provider == "gemini":
            return self._gemini_embed_batch(texts)
        return self._openai_embed_batch(texts)

    def generate(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.1,
        json_object: bool = False,
    ) -> str:
        if self.provider == "gemini":
            return self._gemini_generate(messages, temperature=temperature, json_object=json_object)
        return self._openai_generate(messages, temperature=temperature, json_object=json_object)

    def _openai_embed_batch(self, texts: List[str]) -> List[List[float]]:
        cleaned = [t.strip() if t.strip() else " " for t in texts]
        for attempt in range(self.max_retries):
            try:
                response = self.openai_client.embeddings.create(
                    input=cleaned,
                    model=self.embedding_model,
                )
                return [item.embedding for item in response.data]
            except RateLimitError:
                wait = 2 ** attempt
                logger.warning("OpenAI rate limited, retrying in %ss", wait)
                time.sleep(wait)
            except APIError:
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(2 ** attempt)
        raise RuntimeError("Failed to generate OpenAI embeddings after retries")

    def _openai_generate(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float,
        json_object: bool,
    ) -> str:
        kwargs: Dict[str, Any] = {
            "model": self.generation_model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_object:
            kwargs["response_format"] = {"type": "json_object"}
        response = self.openai_client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    def _gemini_embed_batch(self, texts: List[str]) -> List[List[float]]:
        cleaned = [t.strip() if t.strip() else " " for t in texts]
        model = self._gemini_model_name(self.embedding_model)
        url = f"https://generativelanguage.googleapis.com/v1beta/{model}:embedContent"
        embeddings = []
        for index, text in enumerate(cleaned):
            payload = {
                "model": model,
                "content": {"parts": [{"text": text}]},
            }
            data = self._gemini_post(url, payload)
            embeddings.append(data.get("embedding", {}).get("values", []))
            if settings.GEMINI_EMBEDDING_DELAY_SECONDS and index < len(cleaned) - 1:
                time.sleep(settings.GEMINI_EMBEDDING_DELAY_SECONDS)
        return embeddings

    def _gemini_generate(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float,
        json_object: bool,
    ) -> str:
        model = self._gemini_model_name(self.generation_model)
        url = f"https://generativelanguage.googleapis.com/v1beta/{model}:generateContent"
        system_instruction = self._first_message(messages, "system")
        user_text = "\n\n".join(m["content"] for m in messages if m.get("role") != "system")
        payload: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": user_text}]}],
            "generationConfig": {"temperature": temperature},
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        if json_object:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        data = self._gemini_post(url, payload)
        candidates = data.get("candidates") or []
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        return "".join(part.get("text", "") for part in parts)

    def _gemini_post(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is required when AI_PROVIDER=gemini")

        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": settings.GEMINI_API_KEY,
        }
        for attempt in range(self.max_retries):
            try:
                response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=120)
            except requests.RequestException as exc:
                if attempt == self.max_retries - 1:
                    raise
                wait = min(10 * (attempt + 1), 60)
                logger.warning("Gemini API request failed (%s), retrying in %ss", exc, wait)
                time.sleep(wait)
                continue

            if response.status_code in {429, 500, 502, 503, 504} and attempt < self.max_retries - 1:
                wait = self._retry_delay(response, attempt)
                logger.warning("Gemini API returned %s, retrying in %ss", response.status_code, wait)
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response.json()
        raise RuntimeError("Failed to call Gemini API after retries")

    @staticmethod
    def _gemini_model_name(model: str) -> str:
        return model if model.startswith("models/") else f"models/{model}"

    @staticmethod
    def _retry_delay(response: requests.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass

        try:
            details = response.json().get("error", {}).get("details", [])
            for detail in details:
                retry_delay = detail.get("retryDelay")
                if retry_delay and retry_delay.endswith("s"):
                    return float(retry_delay[:-1])
        except (ValueError, TypeError, AttributeError):
            pass

        if response.status_code == 429:
            return min(15 * (attempt + 1), 60)
        return 2 ** attempt

    @staticmethod
    def _first_message(messages: List[Dict[str, str]], role: str) -> Optional[str]:
        for message in messages:
            if message.get("role") == role:
                return message.get("content", "")
        return None


ai_client = AIClient()
