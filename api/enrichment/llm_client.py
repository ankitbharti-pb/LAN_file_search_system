"""LLM client abstraction for document enrichment."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from openai import AsyncOpenAI

from config.settings import settings

logger = logging.getLogger(__name__)

# Pricing per 1M tokens: (input, output)
OPENAI_PRICING: dict[str, tuple[float, float]] = {
    # GPT-5 family
    "gpt-5.2": (1.75, 14.00),
    "gpt-5.1": (1.25, 10.00),
    "gpt-5": (1.25, 10.00),
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5-nano": (0.05, 0.40),
    # GPT-4.1 family
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    # GPT-4o family
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    # o-series
    "o3": (2.00, 8.00),
    "o4-mini": (1.10, 4.40),
}

GEMINI_PRICING: dict[str, tuple[float, float]] = {
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.5-pro": (1.25, 10.00),
}


def _get_pricing(model: str, pricing_table: dict[str, tuple[float, float]]) -> tuple[float, float]:
    """Look up pricing for a model, falling back to prefix matching."""
    if model in pricing_table:
        return pricing_table[model]
    # Prefix match for versioned model names (e.g. "gpt-4.1-mini-2025-04-14")
    for key in sorted(pricing_table, key=len, reverse=True):
        if model.startswith(key):
            return pricing_table[key]
    return (0.0, 0.0)


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
                max_completion_tokens=max_tokens,
                temperature=temperature,
            )

            # Log token usage for cost estimation
            if response.usage:
                u = response.usage
                price_in, price_out = _get_pricing(self.model, OPENAI_PRICING)
                cost_input = (u.prompt_tokens / 1_000_000) * price_in
                cost_output = (u.completion_tokens / 1_000_000) * price_out
                cost_total = cost_input + cost_output
                logger.info(
                    f"[LLM Usage] model={self.model} "
                    f"prompt_tokens={u.prompt_tokens} "
                    f"completion_tokens={u.completion_tokens} "
                    f"total_tokens={u.total_tokens} "
                    f"cost=${cost_total:.6f}"
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

            # Log token usage for cost estimation
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                um = response.usage_metadata
                prompt_tokens = getattr(um, "prompt_token_count", 0) or 0
                completion_tokens = getattr(um, "candidates_token_count", 0) or 0
                total_tokens = getattr(um, "total_token_count", 0) or 0
                price_in, price_out = _get_pricing(self.model, GEMINI_PRICING)
                cost_input = (prompt_tokens / 1_000_000) * price_in
                cost_output = (completion_tokens / 1_000_000) * price_out
                cost_total = cost_input + cost_output
                logger.info(
                    f"[LLM Usage] model={self.model} "
                    f"prompt_tokens={prompt_tokens} "
                    f"completion_tokens={completion_tokens} "
                    f"total_tokens={total_tokens} "
                    f"cost=${cost_total:.6f}"
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


def get_enrichment_llm_client() -> LLMClient:
    """Get LLM client configured for chunk enrichment."""
    model = settings.enrichment_model or None
    if settings.llm_provider == "openai":
        return OpenAIClient(model=model)
    elif settings.llm_provider == "gemini":
        return GeminiClient(model=model)
    else:
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


def get_synthesis_llm_client() -> LLMClient:
    """Get LLM client configured for response synthesis."""
    model = settings.synthesis_model or None
    if settings.llm_provider == "openai":
        return OpenAIClient(model=model)
    elif settings.llm_provider == "gemini":
        return GeminiClient(model=model)
    else:
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


# Default client instance
llm_client = get_llm_client()
