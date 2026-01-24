"""LLM client abstraction for document enrichment."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from openai import AsyncOpenAI

from config.settings import settings

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.3,
    ) -> str:
        """Generate a completion from the LLM."""
        pass

    async def complete_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 2000,
    ) -> dict[str, Any]:
        """Generate a JSON response from the LLM."""
        response = await self.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=0.2,  # Lower temperature for JSON
        )

        # Parse JSON from response
        try:
            # Try to extract JSON from markdown code blocks
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                if end > start:
                    response = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                if end > start:
                    response = response[start:end].strip()

            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            logger.debug(f"Raw response: {response[:500]}")
            return {}


class OpenAIClient(LLMClient):
    """OpenAI API client implementation."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_model
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        """Lazy load the OpenAI client."""
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.3,
    ) -> str:
        """Generate a completion using OpenAI API."""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            return response.choices[0].message.content or ""

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise


class GeminiClient(LLMClient):
    """Google Gemini API client implementation."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.gemini_model
        self._model_instance = None

    def _get_model(self):
        """Lazy load the Gemini model."""
        if self._model_instance is None:
            try:
                import google.generativeai as genai

                genai.configure(api_key=self.api_key)
                self._model_instance = genai.GenerativeModel(self.model)
            except ImportError:
                raise ImportError(
                    "google-generativeai not installed. "
                    "Install with: pip install google-generativeai"
                )
        return self._model_instance

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.3,
    ) -> str:
        """Generate a completion using Gemini API."""
        model = self._get_model()

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        try:
            response = await model.generate_content_async(
                full_prompt,
                generation_config={
                    "max_output_tokens": max_tokens,
                    "temperature": temperature,
                },
            )

            return response.text or ""

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise


def get_llm_client() -> LLMClient:
    """Factory function to get the configured LLM client."""
    if settings.llm_provider == "openai":
        return OpenAIClient()
    elif settings.llm_provider == "gemini":
        return GeminiClient()
    else:
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


# Default client instance
llm_client = get_llm_client()
