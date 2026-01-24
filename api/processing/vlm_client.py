"""VLM clients for content extraction with multiple provider support."""

import base64
import logging
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


class VLMClient(ABC):
    """Abstract base class for VLM providers."""

    @abstractmethod
    async def analyze_image(self, image_path: Path, prompt: str) -> str:
        """Send image to VLM for analysis.

        Args:
            image_path: Path to the image file
            prompt: Text prompt for the VLM

        Returns:
            VLM response text
        """
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the VLM service is available.

        Returns:
            True if service is reachable and model is available
        """
        pass

    async def extract_table(self, image_path: Path) -> str:
        """Extract table content as markdown.

        Args:
            image_path: Path to table region image

        Returns:
            Markdown-formatted table
        """
        prompt = """Extract the table from this image as a markdown table.
- Use | for column separators
- Include header row with --- separator
- Preserve all data accurately
- If cells span multiple rows/columns, note it
Output ONLY the markdown table, no explanations."""
        return await self.analyze_image(image_path, prompt)

    async def describe_figure(self, image_path: Path) -> str:
        """Generate figure description.

        Args:
            image_path: Path to figure region image

        Returns:
            Text description of the figure
        """
        prompt = """Describe this figure/image from a document.
- What type of visualization is it? (chart, diagram, photo, etc.)
- What does it show?
- Key data points or elements visible
- Any labels, legends, or annotations
Be concise but complete."""
        return await self.analyze_image(image_path, prompt)

    async def extract_formula(self, image_path: Path) -> str:
        """Extract formula as LaTeX.

        Args:
            image_path: Path to formula region image

        Returns:
            LaTeX representation of the formula
        """
        prompt = """Extract the mathematical formula from this image as LaTeX.
- Use standard LaTeX notation
- Output ONLY the LaTeX code, wrapped in $$ delimiters
- If multiple formulas, separate with newlines
Example: $$E = mc^2$$"""
        return await self.analyze_image(image_path, prompt)

    async def ocr_text(self, image_path: Path) -> str:
        """OCR text from image region.

        Args:
            image_path: Path to text region image

        Returns:
            Extracted text content
        """
        prompt = """Extract all text from this image accurately.
- Preserve paragraph structure
- Maintain reading order
- Include all visible text, even small or faint
Output ONLY the extracted text."""
        return await self.analyze_image(image_path, prompt)


class OllamaVLMClient(VLMClient):
    """Ollama VLM client for local inference."""

    def __init__(self, base_url: str, model: str, timeout: float):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy-load async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def analyze_image(self, image_path: Path, prompt: str) -> str:
        """Send image to Ollama VLM for analysis."""
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Load and encode image as base64
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        logger.debug(f"Sending image to Ollama VLM: {image_path.name}")

        response = await self.client.post(
            "/api/chat",
            json={
                "model": self.model,
                "messages": [{
                    "role": "user",
                    "content": prompt,
                    "images": [image_data],
                }],
                "stream": False,
            },
        )
        response.raise_for_status()

        result = response.json()
        content = result.get("message", {}).get("content", "")
        logger.debug(f"Ollama VLM response length: {len(content)} chars")

        return content

    async def is_available(self) -> bool:
        """Check if Ollama server is available and model is loaded."""
        try:
            response = await self.client.get("/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                return any(self.model in m.get("name", "") for m in models)
        except Exception:
            pass
        return False


class HuggingFaceVLMClient(VLMClient):
    """HuggingFace Inference API client for cloud inference via OpenAI-compatible router."""

    def __init__(self, api_key: str, model: str, timeout: float):
        # Parse model string: "repo/model:provider" -> just use "repo/model"
        # HuggingFace router handles provider routing automatically
        if ":" in model:
            self.model_id = model.rsplit(":", 1)[0]
        else:
            self.model_id = model
        self.model = model  # Keep full string for reference
        self.timeout = timeout
        self._api_key = api_key
        self._client = None

    @property
    def client(self):
        """Lazy-load OpenAI client configured for HuggingFace router."""
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                base_url="https://router.huggingface.co/v1",
                api_key=self._api_key,
                timeout=self.timeout,
            )
        return self._client

    async def analyze_image(self, image_path: Path, prompt: str) -> str:
        """Send image to HuggingFace VLM for analysis."""
        import asyncio

        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Encode image as base64 data URL
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # Determine MIME type from extension
        ext = image_path.suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(ext, "image/png")
        image_url = f"data:{mime_type};base64,{image_data}"

        logger.debug(f"Sending image to HuggingFace VLM: {image_path.name}")

        # OpenAI client is synchronous, wrap in executor
        def _call_hf():
            return self.client.chat.completions.create(
                model=self.model_id,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": prompt},
                    ],
                }],
                max_tokens=1024,
            )

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, _call_hf)

        content = response.choices[0].message.content
        logger.debug(f"HuggingFace VLM response length: {len(content)} chars")

        return content

    async def is_available(self) -> bool:
        """Check if HuggingFace API is available."""
        if not self._api_key:
            logger.warning("HuggingFace API key not configured")
            return False
        # HuggingFace router is generally available if API key is set
        return True


def get_vlm_client() -> VLMClient:
    """Factory function to get the configured VLM client.

    Returns:
        VLMClient instance based on settings.vlm_provider
    """
    provider = settings.vlm_provider

    if provider == "huggingface":
        logger.info(f"Using HuggingFace VLM: {settings.huggingface_vlm_model}")
        return HuggingFaceVLMClient(
            api_key=settings.huggingface_api_key,
            model=settings.huggingface_vlm_model,
            timeout=settings.huggingface_timeout,
        )
    else:
        logger.info(f"Using Ollama VLM: {settings.ollama_model}")
        return OllamaVLMClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout=settings.ollama_timeout,
        )


# Global instance using factory
vlm_client = get_vlm_client()
